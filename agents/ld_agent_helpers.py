"""
Helper functions for LaunchDarkly AI agents - simplified version
"""
import asyncio
import json
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

                # Execute agent with tracking
                response = await config_manager.track_metrics_async(
                    tracker,
                    lambda: agent.ainvoke(initial_state),
                    model_name=agent_config.model.name,
                    user_id=user_id,
                    user_context=user_context,
                    prev_message_count=prev_message_count
                )

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

                                # Try to extract details
                                if hasattr(tool_call, 'args'):
                                    tool_details.append({
                                        "tool": tool_name,
                                        "args": tool_call.args
                                    })

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