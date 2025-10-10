"""
Helper functions for LaunchDarkly AI agents - simplified version
"""
import asyncio
import json
import time
from typing import List, Any, Tuple, Optional
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from ldai.tracker import TokenUsage
from utils.logger import log_student

# Simple rate limiter to prevent hitting API limits
_last_llm_call_time = 0
_min_call_interval = 1.0  # 1 second between LLM calls

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
    """Map LaunchDarkly provider names to LangChain provider names."""
    provider_mapping = {
        'gemini': 'google_genai',
        'anthropic': 'anthropic',
        'openai': 'openai',
        'mistral': 'mistralai'
    }
    lower_provider = provider_name.lower()
    return provider_mapping.get(lower_provider, lower_provider)


async def create_agent_with_fresh_config(
    config_manager,
    config_key: str,
    user_id: str,
    user_context: dict,
    tools: List[Any] = None
) -> Tuple[Any, Any, bool]:
    """
    Create a LangChain agent with LaunchDarkly AI config.

    Returns:
        - agent: The created React agent
        - tracker: LaunchDarkly tracker for metrics
        - disabled: True if the config is disabled
    """
    if tools is None:
        tools = []

    try:
        # Fetch config from LaunchDarkly
        agent_config = await config_manager.get_config(
            user_id=user_id,
            config_key=config_key,
            user_context=user_context
        )

        if not agent_config.enabled:
            return None, None, True

        # Map provider and create LangChain model
        langchain_provider = map_provider_to_langchain(agent_config.provider.name)
        llm = init_chat_model(
            model=agent_config.model.name,
            model_provider=langchain_provider,
        )

        # Extract max_tool_calls from LaunchDarkly config
        max_tool_calls = 5  # Default value
        try:
            config_dict = agent_config.to_dict()
            if 'model' in config_dict and 'custom' in config_dict['model'] and config_dict['model']['custom']:
                custom_params = config_dict['model']['custom']
                if 'max_tool_calls' in custom_params:
                    max_tool_calls = custom_params['max_tool_calls']
        except Exception as e:
            log_student(f"DEBUG: Error extracting max_tool_calls: {e}")

        # Create React agent with instructions
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=agent_config.instructions
        )

        return agent, agent_config.tracker, False

    except Exception as e:
        log_student(f"ERROR in create_agent_with_fresh_config: {e}")
        return None, None, True


def create_simple_agent_wrapper(config_manager, config_key: str, tools: List[Any] = None):
    """
    Create an agent wrapper that fetches config on each invocation.

    Returns an object with an invoke() method that:
    1. Fetches LaunchDarkly config
    2. Creates React agent with instructions
    3. Executes the agent with proper tracking
    """
    if tools is None:
        tools = []

    class LaunchDarklyAgent:
        def __init__(self):
            self.max_tool_calls = 15  # Default value

        async def ainvoke(self, request_data: dict) -> dict:
            """
            Async invocation - fetches config and executes without blocking event loop
            """
            try:
                # Extract request parameters
                user_input = request_data.get("user_input", "")
                user_id = request_data.get("user_id", "agent_user")
                user_context = request_data.get("user_context", {})
                messages = request_data.get("messages", [])

                # Create agent with config
                agent, tracker, disabled = await create_agent_with_fresh_config(
                    config_manager=config_manager,
                    config_key=config_key,
                    user_id=user_id,
                    user_context=user_context,
                    tools=tools
                )

                if disabled:
                    log_student(f"{config_key}: AI Config is disabled")
                    return {
                        "user_input": user_input,
                        "response": f"AI Config {config_key} is disabled",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                # Prepare messages for agent
                if messages:
                    agent_messages = messages
                else:
                    from langchain_core.messages import HumanMessage
                    agent_messages = [HumanMessage(content=user_input)]

                # Build state
                initial_state = {"messages": agent_messages}
                prev_message_count = len(agent_messages)

                # Get agent configuration for tracking
                agent_config = await config_manager.get_config(
                    user_id=user_id,
                    config_key=config_key,
                    user_context=user_context
                )

                # Apply rate limiting before LLM call
                _rate_limit_llm_call()

                # Execute agent with tracking
                start_time = time.time()
                try:
                    # Execute agent
                    response = await agent.ainvoke(initial_state)

                    # Track success and latency
                    tracker.track_success()
                    latency_ms = int((time.time() - start_time) * 1000)
                    if hasattr(tracker, 'track_latency_ms'):
                        tracker.track_latency_ms(latency_ms)

                    # Extract token usage from new messages
                    new_messages = response['messages'][prev_message_count:]
                    total_input = 0
                    total_output = 0

                    for msg in new_messages:
                        if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                            total_input += msg.usage_metadata.get('input_tokens', 0)
                            total_output += msg.usage_metadata.get('output_tokens', 0)

                    # Track tokens if found
                    if total_input > 0 or total_output > 0:
                        token_usage = TokenUsage(
                            input=total_input,
                            output=total_output,
                            total=total_input + total_output
                        )
                        tracker.track_tokens(token_usage)
                        log_student(f"AGENT TOKENS: {token_usage.total} tokens ({token_usage.input} in, {token_usage.output} out)")

                        # Track cost metric with AI Config metadata for experiment attribution
                        from utils.cost_calculator import calculate_cost
                        cost = calculate_cost(agent_config.model.name, total_input, total_output)
                        if cost > 0:
                            # Use centralized context builder to ensure exact match with AI Config evaluation
                            ld_context = config_manager.build_context(user_id, user_context)

                            # Track cost with metadata for experiment attribution
                            config_manager.track_cost_metric(agent_config, ld_context, cost, config_key)
                            log_student(f"COST TRACKING: ${cost:.6f} for {agent_config.model.name}")

                except Exception as e:
                    tracker.track_error()
                    raise

                # Extract new messages
                new_messages = response['messages'][prev_message_count:]

                # Parse response
                ai_response = ""
                tool_calls_summary = []
                tool_details = []

                for msg in new_messages:
                    # Get AI message content
                    if hasattr(msg, 'content') and msg.content:
                        if isinstance(msg.content, list):
                            for content_item in msg.content:
                                if hasattr(content_item, 'text'):
                                    ai_response += content_item.text + " "
                        else:
                            ai_response += str(msg.content) + " "

                    # Track tool calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if hasattr(tool_call, 'name'):
                                tool_name = tool_call.name
                                tool_calls_summary.append(tool_name)

                                # Try to extract details with search query
                                if hasattr(tool_call, 'args'):
                                    detail = {
                                        "name": tool_name,
                                        "args": tool_call.args
                                    }
                                    # Extract search query from args if present
                                    if isinstance(tool_call.args, dict):
                                        if 'query' in tool_call.args:
                                            detail["search_query"] = tool_call.args['query']
                                        elif 'search_query' in tool_call.args:
                                            detail["search_query"] = tool_call.args['search_query']
                                    tool_details.append(detail)

                return {
                    "user_input": user_input,
                    "response": ai_response.strip() if ai_response else "I understand your question. Let me help you with that.",
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

        def invoke(self, request_data: dict) -> dict:
            """
            Synchronous invocation - runs async code in new event loop
            """
            try:
                # Try to run in existing event loop first
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, create task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.ainvoke(request_data))
                        return future.result()
                except RuntimeError:
                    # No event loop, create one
                    return asyncio.run(self.ainvoke(request_data))
            except Exception as e:
                log_student(f"SYNC INVOKE ERROR in {config_key}: {e}")
                return {
                    "user_input": request_data.get("user_input", ""),
                    "response": f"I apologize, but I encountered an error: {e}",
                    "tool_calls": [],
                    "tool_details": [],
                    "messages": []
                }

    return LaunchDarklyAgent()