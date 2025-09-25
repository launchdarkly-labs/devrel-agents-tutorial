"""
Shared helper functions for LaunchDarkly AI agents following the proper pattern
"""
import asyncio
from typing import List, Any, Tuple, Optional
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from ldai.tracker import TokenUsage
from utils.logger import log_student


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




def track_langgraph_metrics(tracker, func):
    """
    Track LangGraph agent operations with LaunchDarkly metrics.
    Based on the pattern from your examples.
    """
    try:
        result = tracker.track_duration_of(func)
        tracker.track_success()

        # For LangGraph agents, usage_metadata is included on all messages that used AI
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        if "messages" in result:
            for message in result['messages']:
                # Check for usage_metadata directly on the message
                if hasattr(message, "usage_metadata") and message.usage_metadata:
                    usage_data = message.usage_metadata
                    total_input_tokens += usage_data.get("input_tokens", 0)
                    total_output_tokens += usage_data.get("output_tokens", 0)
                    total_tokens += usage_data.get("total_tokens", 0)

        if total_tokens > 0:
            token_usage = TokenUsage(
                input=total_input_tokens,
                output=total_output_tokens,
                total=total_tokens
            )
            tracker.track_tokens(token_usage)
    except Exception:
        tracker.track_error()
        raise
    return result


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
        max_tool_calls = 15  # Default value
        try:
            config_dict = agent_config.to_dict()
            if 'model' in config_dict and 'custom' in config_dict['model'] and config_dict['model']['custom']:
                custom_params = config_dict['model']['custom']
                if 'max_tool_calls' in custom_params:
                    max_tool_calls = custom_params['max_tool_calls']
        except Exception as e:
            log_student(f"DEBUG: Error extracting max_tool_calls in create_agent_with_fresh_config: {e}")


        # Create React agent with instructions
        # Note: LangGraph's create_react_agent handles max iterations internally
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=agent_config.instructions
        )

        return agent, agent_config.tracker, False

    except Exception as e:
        log_student(f"Error creating agent {config_key}: {e}")
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

        def invoke(self, request_data: dict) -> dict:
            """
            Main agent invocation - fetches config and executes
            """
            try:
                # Extract request parameters
                user_input = request_data.get("user_input", "")
                user_id = request_data.get("user_id", "agent_user")
                user_context = request_data.get("user_context", {})
                messages = request_data.get("messages", [])

                # Create agent with config
                agent, tracker, disabled = asyncio.run(create_agent_with_fresh_config(
                    config_manager=config_manager,
                    config_key=config_key,
                    user_id=user_id,
                    user_context=user_context,
                    tools=tools
                ))

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

                # Prepare initial state for agent
                initial_state = {
                    "messages": agent_messages
                }

                # Get max_tool_calls from LaunchDarkly config by fetching it fresh
                agent_config = asyncio.run(config_manager.get_config(
                    user_id=user_id,
                    config_key=config_key,
                    user_context=user_context
                ))

                max_tool_calls = 15  # Default

                # Extract max_tool_calls from LaunchDarkly config
                # Based on SDK test: max_tool_calls is in config_dict['model']['custom']['max_tool_calls']
                if agent_config:
                    try:
                        config_dict = agent_config.to_dict()
                        if 'model' in config_dict and 'custom' in config_dict['model'] and config_dict['model']['custom']:
                            custom_params = config_dict['model']['custom']
                            if 'max_tool_calls' in custom_params:
                                max_tool_calls = custom_params['max_tool_calls']
                                pass  # Successfully extracted max_tool_calls
                            else:
                                pass  # max_tool_calls not in custom params
                        else:
                            log_student(f"DEBUG: No model.custom found in config_dict")
                    except Exception as e:
                        log_student(f"DEBUG: Error extracting max_tool_calls: {e}")

                # Execute agent with metrics tracking and recursion limit
                # LangGraph formula: recursion_limit = 2 * max_tool_calls + 1
                # Each tool call requires 2 steps: LLM -> Tool -> LLM
                recursion_limit = 2 * max_tool_calls + 1
        
                response = track_langgraph_metrics(
                    tracker,
                    lambda: agent.invoke(initial_state, config={"recursion_limit": recursion_limit})
                )

                # Extract final response and tool calls
                final_response = response["messages"][-1].content if response["messages"] else ""

                tool_calls = []
                tool_details = []
                for message in response["messages"]:
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.get('name', 'unknown')
                            tool_args = tool_call.get('args', {})
                            tool_calls.append(tool_name)

                            # Extract search query from tool arguments (multiple possible field names)
                            search_query = (
                                tool_args.get('query', '') or
                                tool_args.get('search_query', '') or
                                tool_args.get('q', '') or
                                str(tool_args) if len(str(tool_args)) < 100 else ''
                            )

                            tool_details.append({
                                "name": tool_name,
                                "search_query": search_query if search_query else None,
                                "args": tool_args
                            })

                return {
                    "user_input": user_input,
                    "response": final_response,
                    "tool_calls": tool_calls,
                    "tool_details": tool_details,
                    "messages": response["messages"]
                }

            except Exception as e:
                log_student(f"Error in {config_key} agent: {e}")
                return {
                    "user_input": user_input,
                    "response": f"I apologize, but I encountered an error: {e}",
                    "tool_calls": [],
                    "tool_details": [],
                    "messages": []
                }

    return LaunchDarklyAgent()