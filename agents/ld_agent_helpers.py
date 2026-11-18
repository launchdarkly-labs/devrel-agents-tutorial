"""
LaunchDarkly AI agent helpers.

Creates agents with dynamic configuration from LaunchDarkly AI Configs.
Routes between Bedrock (SSO) and direct API providers based on AUTH_METHOD.
"""
import time
import os
from typing import List, Any, Tuple
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from utils.logger import log_student
from utils.bedrock_helpers import ensure_bedrock_inference_profile
from langchain_aws import ChatBedrockConverse
import boto3

# Exception for max tool calls exceeded
class MaxToolCallsExceeded(Exception):
    """Raised when agent exceeds max_tool_calls limit from LaunchDarkly"""
    pass


# Tool call counter for tracking invocations
class ToolCallCounter:
    """Shared counter for tracking tool invocations across all tools"""
    def __init__(self, max_calls: int):
        self.count = 0
        self.max_calls = max_calls

    def increment(self):
        """Increment counter and raise exception if limit exceeded"""
        self.count += 1
        if self.count > self.max_calls:
            raise MaxToolCallsExceeded(
                f"Tool call limit of {self.max_calls} exceeded. "
                f"Please simplify your request or increase max_tool_calls in LaunchDarkly config."
            )


# Simple rate limiter to prevent hitting API limits
_last_llm_call_time = 0
_min_call_interval = 1.0  # 1 second between LLM calls

def create_bedrock_chat_model(model_id: str, session: boto3.Session, region: str, **kwargs):
    """
    Create ChatBedrockConverse model with auto-correction.

    Auto-corrects direct model IDs to inference profiles.
    Region from BEDROCK_INFERENCE_REGION env var or AWS_REGION.
    """
    corrected_model_id = ensure_bedrock_inference_profile(model_id, region)

    log_student(f"BEDROCK: Creating model {corrected_model_id} in region {region}")

    model = ChatBedrockConverse(
        client=session.client(service_name='bedrock-runtime', region_name=region),
        model_id=corrected_model_id,
        region_name=region,
        **kwargs
    )

    log_student(f"BEDROCK: Successfully created {corrected_model_id}")
    return model

def _rate_limit_llm_call():
    """Simple rate limiter for LLM calls"""
    global _last_llm_call_time
    current_time = time.time()
    time_since_last_call = current_time - _last_llm_call_time

    if time_since_last_call < _min_call_interval:
        sleep_time = _min_call_interval - time_since_last_call
        log_student(f"Rate limiting: waiting {sleep_time:.2f}s")
        time.sleep(sleep_time)

    _last_llm_call_time = time.time()


def map_provider_to_langchain(provider_name):
    """Map LaunchDarkly provider names (e.g. 'Anthropic', 'bedrock:anthropic') to LangChain provider names."""
    provider = provider_name.lower()
    if provider.startswith('bedrock:'):
        return 'bedrock'
    return {'gemini': 'google_genai', 'mistral': 'mistralai'}.get(provider, provider)


def create_chat_model(provider_name: str, model_name: str, config_manager):
    """
    Create the LangChain chat model for a LaunchDarkly AI Config.

    Anthropic and Bedrock models go through Bedrock when AUTH_METHOD=sso,
    otherwise through their direct API.
    """
    provider = map_provider_to_langchain(provider_name)

    if provider in ('anthropic', 'bedrock') and os.getenv('AUTH_METHOD', 'api-key').lower() == 'sso':
        return create_bedrock_chat_model(
            model_id=model_name,
            session=config_manager.boto3_session,
            region=config_manager.aws_region
        )

    # GPT-6 models accept function tools only on the Responses API
    responses_api = {"use_responses_api": True} if provider == "openai" else {}
    return init_chat_model(model=model_name, model_provider=provider, **responses_api)


def ci_safe_provider_and_model(provider_name: str, model_name: str) -> tuple[str, str]:
    """Under CI_SAFE_MODE, use OpenAI when only an OpenAI key is available."""
    ci = os.getenv("CI_SAFE_MODE", "").lower() in {"1", "true", "yes"}
    if ci and not os.getenv("ANTHROPIC_API_KEY") and os.getenv("OPENAI_API_KEY"):
        return ("openai", "gpt-6-luna")
    return (provider_name, model_name)


def wrap_tool_with_counter(tool: Any, counter: ToolCallCounter) -> Any:
    """
    Wrap a tool to track invocation count.

    Each time the tool is called, the counter is incremented.
    If max_tool_calls is exceeded, MaxToolCallsExceeded is raised.

    Uses a closure-based approach to avoid pickling issues.
    """
    def count_call(kwargs):
        counter.increment()
        query = kwargs.get('query') or kwargs.get('search_query')
        query_info = f" | Query: '{query}'" if query else ""
        log_student(f"TOOL CALL #{counter.count}/{counter.max_calls}: {tool.name}{query_info}")

    def counted_run(**kwargs) -> str:
        count_call(kwargs)
        return tool._run(**kwargs)

    async def counted_arun(**kwargs) -> str:
        count_call(kwargs)
        return await tool._arun(**kwargs)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        func=counted_run,
        coroutine=counted_arun,
        args_schema=tool.args_schema
    )


async def create_agent_with_fresh_config(
    config_manager,
    config_key: str,
    user_id: str,
    user_context: dict,
    tools: List[Any]
) -> Tuple[Any, Any, int]:
    """
    Create LangChain agent with LaunchDarkly AI Config.

    Routes to Bedrock (AUTH_METHOD=sso) or direct API based on config.
    Returns: (agent, served_config, recursion_limit)
    """
    agent_config = await config_manager.get_config(
        user_id=user_id,
        config_key=config_key,
        user_context=user_context
    )

    llm = create_chat_model(agent_config.provider_name, agent_config.model_name, config_manager)
    log_student(f"ROUTING: Using {agent_config.provider_name} for {agent_config.model_name}")

    # Extract max_tool_calls from LaunchDarkly config
    max_tool_calls = 5  # Default value
    if 'max_tool_calls' in agent_config.custom:
        max_tool_calls = int(agent_config.custom['max_tool_calls'])
        log_student(f"EXTRACTED max_tool_calls from LaunchDarkly: {max_tool_calls}")

    # Wrap tools with call counter to track invocations
    counter = ToolCallCounter(max_calls=max_tool_calls)
    wrapped_tools = [wrap_tool_with_counter(tool, counter) for tool in tools]

    # Calculate effective recursion limit
    # Formula: max_tool_calls * 3 + 10 headroom
    # Each tool call cycle: think → tool_call → tool_result → think
    effective_recursion_limit = max_tool_calls * 3 + 10
    log_student(f"CONFIG: max_tool_calls={max_tool_calls}, effective_recursion_limit={effective_recursion_limit}")

    agent = create_react_agent(
        model=llm,
        tools=wrapped_tools,
        prompt=agent_config.instructions
    )

    return agent, agent_config, effective_recursion_limit


def create_simple_agent_wrapper(config_manager, config_key: str, tools: List[Any]):
    """
    Create agent wrapper that fetches fresh LaunchDarkly config on each invocation.

    Enables dynamic A/B testing and real-time config changes without restarts.
    Tracks tokens, costs, and errors automatically.
    """
    class LaunchDarklyAgent:
        async def ainvoke(self, request_data: dict) -> dict:
            """
            Async invocation - fetches config and executes without blocking event loop
            """
            user_input = request_data.get("user_input", "")
            try:
                user_id = request_data.get("user_id", "agent_user")
                user_context = request_data.get("user_context", {})
                agent_messages = request_data.get("messages") or [HumanMessage(content=user_input)]

                agent, served, effective_recursion_limit = await create_agent_with_fresh_config(
                    config_manager=config_manager,
                    config_key=config_key,
                    user_id=user_id,
                    user_context=user_context,
                    tools=tools
                )

                initial_state = {"messages": agent_messages}
                prev_message_count = len(agent_messages)

                ld_context = config_manager.build_context(user_id, user_context)

                # Apply rate limiting before LLM call
                _rate_limit_llm_call()

                async def run_agent():
                    log_student(f"EXECUTING AGENT with recursion_limit={effective_recursion_limit}")
                    try:
                        result = await agent.ainvoke(initial_state, {"recursion_limit": effective_recursion_limit})
                    except MaxToolCallsExceeded as exc:
                        # Returned, not raised: reaching the tool limit is expected and isn't a generation error.
                        return exc, {}

                    usage = {"input_tokens": 0, "output_tokens": 0}
                    for msg in result['messages'][prev_message_count:]:
                        if getattr(msg, 'usage_metadata', None):
                            usage["input_tokens"] += msg.usage_metadata.get('input_tokens', 0)
                            usage["output_tokens"] += msg.usage_metadata.get('output_tokens', 0)
                    return result, usage

                response = await config_manager.track(served, ld_context, run_agent, user_input)

                if isinstance(response, MaxToolCallsExceeded):
                    log_student(f"TOOL LIMIT REACHED: {response}")
                    # Return friendly message explaining the limit
                    return {
                        "user_input": user_input,
                        "response": f"I've reached the tool call limit for this request. {response}",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                # Parse the new AI messages into a response and the tool calls made
                ai_response = ""
                tool_calls_summary = []
                tool_details = []

                for msg in response['messages'][prev_message_count:]:
                    if msg.type != 'ai':
                        continue

                    if isinstance(msg.content, list):
                        for content_item in msg.content:
                            if isinstance(content_item, dict) and content_item.get('type') == 'text':
                                ai_response += content_item.get('text', '') + " "
                    elif msg.content:
                        ai_response += str(msg.content) + " "

                    for tool_call in msg.tool_calls:
                        args = tool_call.get('args') or {}
                        detail = {"name": tool_call['name'], "args": args}
                        search_query = args.get('query') or args.get('search_query')
                        if search_query:
                            detail["search_query"] = search_query
                        tool_calls_summary.append(tool_call['name'])
                        tool_details.append(detail)

                return {
                    "user_input": user_input,
                    "response": ai_response.strip() or "I understand your question. Let me help you with that.",
                    "tool_calls": tool_calls_summary,
                    "tool_details": tool_details,
                    "messages": response['messages']
                }

            except Exception as e:
                log_student(f"ERROR in {config_key} ainvoke: {e}")
                import traceback
                log_student(f"Traceback: {traceback.format_exc()}")
                return {
                    "user_input": user_input,
                    "response": f"I apologize, but I encountered an error: {e}",
                    "tool_calls": [],
                    "tool_details": [],
                    "messages": []
                }

    return LaunchDarklyAgent()
