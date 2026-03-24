"""LaunchDarkly AI agent helpers - model creation and metric tracking."""
import asyncio
import nest_asyncio
nest_asyncio.apply()  # Allow nested event loops (fixes FastAPI + asyncio.run conflict)

import time
import os
from typing import List, Any, Tuple
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from ldai.tracker import TokenUsage
from utils.logger import log_student
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import StructuredTool
import boto3


class MaxToolCallsExceeded(Exception):
    """Raised when agent exceeds max_tool_calls limit."""
    pass


class ToolCallCounter:
    """Tracks tool invocations and enforces limits."""
    def __init__(self, max_calls: int):
        self.count = 0
        self.max_calls = max_calls

    def increment(self):
        self.count += 1
        if self.count > self.max_calls:
            raise MaxToolCallsExceeded(
                f"Tool call limit of {self.max_calls} exceeded. "
                "Please simplify your request or increase max_tool_calls in LaunchDarkly."
            )


# Rate limiting
_last_llm_call_time = 0
_min_call_interval = 1.0


def _rate_limit_llm_call():
    """Simple rate limiter for LLM calls."""
    global _last_llm_call_time
    elapsed = time.time() - _last_llm_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    _last_llm_call_time = time.time()


def map_provider_to_langchain(provider_name: str) -> str:
    """Map LaunchDarkly provider names to LangChain."""
    mapping = {
        'anthropic': 'bedrock',
        'bedrock': 'bedrock',
        'gemini': 'google_genai',
        'openai': 'openai',
        'mistral': 'mistralai'
    }
    return mapping.get(provider_name.lower(), provider_name.lower())


def create_bedrock_chat_model(model_id: str, session: boto3.Session, region: str, **kwargs):
    """Create ChatBedrockConverse model with auto-correction for inference profiles."""
    from utils.bedrock_helpers import ensure_bedrock_inference_profile

    corrected_model_id = ensure_bedrock_inference_profile(model_id, region)
    log_student(f"BEDROCK: Creating {corrected_model_id} in {region}")

    client = session.client('bedrock-runtime', region_name=region)
    return ChatBedrockConverse(
        client=client,
        model_id=corrected_model_id,
        region_name=region,
        **kwargs
    )


def create_model_for_config(provider: str, model: str, config_manager, temperature: float = 0.0):
    """Create LangChain chat model based on provider and auth method."""
    from utils.bedrock_helpers import normalize_bedrock_provider

    normalized = normalize_bedrock_provider(provider)
    langchain_provider = map_provider_to_langchain(normalized)

    if langchain_provider == 'bedrock':
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
        if auth_method == 'sso' and hasattr(config_manager, 'boto3_session') and config_manager.boto3_session:
            return create_bedrock_chat_model(
                model_id=model,
                session=config_manager.boto3_session,
                region=config_manager.aws_region,
                temperature=temperature
            )
        else:
            fallback = 'anthropic' if provider.lower() == 'anthropic' else langchain_provider
            return init_chat_model(model=model, model_provider=fallback, temperature=temperature)
    else:
        return init_chat_model(model=model, model_provider=langchain_provider, temperature=temperature)


def extract_token_usage(response) -> dict:
    """Extract token usage from LLM response."""
    if isinstance(response, dict) and "raw" in response and hasattr(response["raw"], "usage_metadata"):
        usage = response["raw"].usage_metadata
        if usage:
            return {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "total": usage.get("total_tokens", 0)
            }
    return {"input": 0, "output": 0, "total": 0}


def wrap_tool_with_counter(tool: Any, counter: ToolCallCounter) -> StructuredTool:
    """Wrap a tool to track and limit invocations."""
    original_run = tool._run if hasattr(tool, '_run') else None
    original_arun = tool._arun if hasattr(tool, '_arun') else None

    def counted_run(**kwargs) -> str:
        counter.increment()
        query = kwargs.get('query') or kwargs.get('search_query', '')
        log_student(f"TOOL CALL #{counter.count}/{counter.max_calls}: {tool.name} | Query: '{query}'")
        if original_run:
            return original_run(**kwargs)
        raise NotImplementedError(f"Tool {tool.name} has no _run method")

    async def counted_arun(**kwargs) -> str:
        counter.increment()
        query = kwargs.get('query') or kwargs.get('search_query', '')
        log_student(f"TOOL CALL #{counter.count}/{counter.max_calls}: {tool.name} | Query: '{query}'")
        if original_arun:
            return await original_arun(**kwargs)
        elif original_run:
            return original_run(**kwargs)
        raise NotImplementedError(f"Tool {tool.name} has no run method")

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        func=counted_run,
        coroutine=counted_arun if original_arun or original_run else None,
        args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None
    )


async def track_langgraph_metrics_async(tracker, coro, prev_message_count=0):
    """Track duration and tokens for async agent invocations."""
    start_time = time.time()
    try:
        result = await coro
        duration_ms = int((time.time() - start_time) * 1000)
        tracker.track_duration(duration_ms)
        tracker.track_success()
        log_student(f"AGENT: duration={duration_ms}ms")

        # Extract tokens from new messages
        total_in, total_out, total = 0, 0, 0
        if "messages" in result:
            for msg in result['messages'][prev_message_count:]:
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage = msg.usage_metadata
                    total_in += usage.get("input_tokens", 0)
                    total_out += usage.get("output_tokens", 0)
                    total += usage.get("total_tokens", 0)

        if total > 0:
            tracker.track_tokens(TokenUsage(input=total_in, output=total_out, total=total))
            log_student(f"AGENT TOKENS: {total} ({total_in} in, {total_out} out)")

        result["_token_usage"] = {"input": total_in, "output": total_out, "total": total}
        return result

    except Exception:
        tracker.track_error()
        raise


async def create_agent_with_fresh_config(
    config_manager,
    config_key: str,
    user_id: str,
    user_context: dict,
    tools: List[Any] = None
) -> Tuple[Any, Any, bool, int]:
    """Create LangChain agent with fresh LaunchDarkly config."""
    tools = tools or []

    try:
        config = await config_manager.get_config(
            user_id=user_id,
            config_key=config_key,
            user_context=user_context
        )

        if not config.enabled:
            return None, None, True, 25

        # Create model
        from utils.bedrock_helpers import normalize_bedrock_provider
        normalized = normalize_bedrock_provider(config.provider.name)
        langchain_provider = map_provider_to_langchain(normalized)

        if langchain_provider == 'bedrock' and os.getenv('AUTH_METHOD', '').lower() == 'sso':
            if not hasattr(config_manager, 'boto3_session') or not config_manager.boto3_session:
                raise ValueError("Bedrock SSO requires AWS session. Run: aws sso login")
            llm = create_bedrock_chat_model(
                model_id=config.model.name,
                session=config_manager.boto3_session,
                region=config_manager.aws_region
            )
            log_student(f"ROUTING: Bedrock SSO - {config.model.name}")
        else:
            fallback = 'anthropic' if config.provider.name.lower() == 'anthropic' else langchain_provider
            llm = init_chat_model(model=config.model.name, model_provider=fallback)
            log_student(f"ROUTING: {fallback} - {config.model.name}")

        # Get max_tool_calls from config
        max_tool_calls = 5
        try:
            config_dict = config.to_dict()
            custom = config_dict.get('model', {}).get('custom', {})
            if 'max_tool_calls' in custom:
                max_tool_calls = int(custom['max_tool_calls'])
        except Exception:
            pass

        # Wrap tools with counter
        counter = ToolCallCounter(max_calls=max_tool_calls)
        wrapped_tools = [wrap_tool_with_counter(t, counter) for t in tools]
        recursion_limit = max_tool_calls * 3 + 10

        log_student(f"CONFIG: max_tool_calls={max_tool_calls}, recursion_limit={recursion_limit}")

        agent = create_react_agent(
            model=llm,
            tools=wrapped_tools,
            prompt=config.instructions
        )

        return agent, config.tracker, False, recursion_limit

    except Exception as e:
        log_student(f"ERROR creating agent: {e}")
        return None, None, True, 25


def create_simple_agent_wrapper(config_manager, config_key: str, tools: List[Any] = None, graph_node_config=None):
    """Create agent wrapper that fetches fresh config on each invocation."""
    tools = tools or []

    class LaunchDarklyAgent:
        async def ainvoke(self, request_data: dict) -> dict:
            user_input = request_data.get("user_input", "")
            user_id = request_data.get("user_id", "agent_user")
            user_context = request_data.get("user_context", {})
            messages = request_data.get("messages", [])

            try:
                agent, tracker, disabled, recursion_limit = await create_agent_with_fresh_config(
                    config_manager=config_manager,
                    config_key=config_key,
                    user_id=user_id,
                    user_context=user_context,
                    tools=tools
                )

                if disabled:
                    log_student(f"{config_key}: disabled")
                    return {
                        "user_input": user_input,
                        "response": f"AI Config {config_key} is disabled",
                        "tool_calls": [], "tool_details": [], "messages": []
                    }

                # Prepare messages
                if not messages:
                    from langchain_core.messages import HumanMessage
                    messages = [HumanMessage(content=user_input)]

                initial_state = {"messages": messages}
                prev_count = len(messages)

                # Use graph node tracker if available
                active_tracker = (
                    graph_node_config.tracker
                    if graph_node_config and hasattr(graph_node_config, 'tracker')
                    else tracker
                )

                _rate_limit_llm_call()

                try:
                    response = await track_langgraph_metrics_async(
                        active_tracker,
                        agent.ainvoke(initial_state, {"recursion_limit": recursion_limit}),
                        prev_count
                    )
                except MaxToolCallsExceeded as e:
                    log_student(f"TOOL LIMIT: {e}")
                    return {
                        "user_input": user_input,
                        "response": f"Tool call limit reached. {str(e)}",
                        "tool_calls": [], "tool_details": [], "messages": []
                    }

                # Parse response
                new_messages = response['messages'][prev_count:]
                ai_response = ""
                tool_calls = []
                tool_details = []

                for msg in new_messages:
                    if hasattr(msg, 'content') and msg.content:
                        if isinstance(msg.content, list):
                            for item in msg.content:
                                if hasattr(item, 'text'):
                                    ai_response += item.text + " "
                        else:
                            ai_response += str(msg.content) + " "

                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', None)
                            if name:
                                tool_calls.append(name)
                                args = tc.get('args', {}) if isinstance(tc, dict) else getattr(tc, 'args', {})
                                tool_details.append({"name": name, "args": args})

                return {
                    "user_input": user_input,
                    "response": ai_response.strip() or "I understand. Let me help you.",
                    "tool_calls": tool_calls,
                    "tool_details": tool_details,
                    "messages": response['messages'],
                    "_token_usage": response.get("_token_usage", {"input": 0, "output": 0, "total": 0})
                }

            except Exception as e:
                log_student(f"ERROR in {config_key}: {e}")
                return {
                    "user_input": user_input,
                    "response": f"Error: {e}",
                    "tool_calls": [], "tool_details": [], "messages": []
                }

        def invoke(self, request_data: dict) -> dict:
            """Sync wrapper for async invocation."""
            try:
                try:
                    asyncio.get_running_loop()
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.ainvoke(request_data))
                        return future.result()
                except RuntimeError:
                    return asyncio.run(self.ainvoke(request_data))
            except Exception as e:
                return {
                    "user_input": request_data.get("user_input", ""),
                    "response": f"Error: {e}",
                    "tool_calls": [], "tool_details": [], "messages": []
                }

    return LaunchDarklyAgent()
