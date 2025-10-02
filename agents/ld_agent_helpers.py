"""
Shared helper functions for LaunchDarkly AI agents following the proper pattern
"""
import asyncio
import time
import json
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

                # Prepare initial state for agent
                initial_state = {
                    "messages": agent_messages
                }

                # Get max_tool_calls from LaunchDarkly config by fetching it fresh
                agent_config = await config_manager.get_config(
                    user_id=user_id,
                    config_key=config_key,
                    user_context=user_context
                )

                # Debug what we got back from LaunchDarkly
                if not agent_config:
                    log_student(f"ERROR: get_config returned None for {config_key}")
                    return {
                        "user_input": user_input,
                        "response": f"Configuration error: {config_key} returned None",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                if not hasattr(agent_config, 'model'):
                    log_student(f"ERROR: agent_config missing 'model' attribute. Type: {type(agent_config)}, attrs: {dir(agent_config) if agent_config else 'None'}")
                    return {
                        "user_input": user_input,
                        "response": f"Configuration error: missing model in {config_key}",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                if not hasattr(agent_config.model, 'name') or not agent_config.model.name:
                    log_student(f"ERROR: agent_config.model missing 'name'. Model: {agent_config.model}, type: {type(agent_config.model)}")
                    return {
                        "user_input": user_input,
                        "response": f"Configuration error: missing model name in {config_key}",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                max_tool_calls = 5  # Default

                # Extract max_tool_calls from LaunchDarkly config
                # Use same path as get_tools_list: model.parameters.custom
                if agent_config:
                    try:
                        config_dict = agent_config.to_dict()
                        log_student(f"DEBUG: LaunchDarkly config keys: {list(config_dict.keys())}")
                        
                        # Check model.parameters.custom (same structure as tools)
                        if 'model' in config_dict and 'parameters' in config_dict['model']:
                            params = config_dict['model']['parameters']
                            
                            # Custom parameters are at the same level as tools
                            if 'custom' in params and params['custom']:
                                custom_params = params['custom']
                                log_student(f"DEBUG: Found custom params: {list(custom_params.keys())}")
                                
                                if 'max_tool_calls' in custom_params:
                                    max_tool_calls = custom_params['max_tool_calls']
                                    log_student(f"DEBUG: Found max_tool_calls={max_tool_calls} in LaunchDarkly")
                            else:
                                log_student(f"DEBUG: No custom params in model.parameters, using default={max_tool_calls}")
                        else:
                            log_student(f"DEBUG: No model.parameters found, using default max_tool_calls={max_tool_calls}")
                    except Exception as e:
                        log_student(f"DEBUG: Error extracting max_tool_calls: {e}, using default={max_tool_calls}")

                # Apply rate limiting before LLM calls
                _rate_limit_llm_call()

                # Create shared tool call counter for both limit enforcement and LaunchDarkly metrics
                tool_counter = {"calls": 0, "names": []}

                def create_limited_tool(tool):
                    """Create a tool that respects LaunchDarkly max_tool_calls limit"""
                    original_run = tool._run

                    def limited_run(*args, **kwargs):
                        if tool_counter["calls"] >= max_tool_calls:
                            log_student(f"DEBUG: Tool '{tool.name}' blocked - LaunchDarkly max_tool_calls limit ({max_tool_calls}) reached")
                            return f"Tool usage limit reached ({max_tool_calls} calls). Please provide your best answer based on available information."

                        tool_counter["calls"] += 1
                        tool_counter["names"].append(tool.name)
                        log_student(f"DEBUG: Tool call {tool_counter['calls']}/{max_tool_calls}: {tool.name}")
                        return original_run(*args, **kwargs)

                    tool._run = limited_run
                    return tool

                # Create tools with LaunchDarkly limit enforcement
                limited_tools = [create_limited_tool(tool) for tool in tools]

                # Create agent with limited tools and natural recursion
                from langchain.chat_models import init_chat_model

                # Debug model config
                if not hasattr(agent_config, 'model') or not hasattr(agent_config.model, 'name'):
                    log_student(f"ERROR: agent_config missing model or model.name: {agent_config}")
                    return {
                        "user_input": user_input,
                        "response": "Configuration error: model not properly configured",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                if not hasattr(agent_config, 'provider') or not hasattr(agent_config.provider, 'name'):
                    log_student(f"ERROR: agent_config missing provider or provider.name: {agent_config}")
                    return {
                        "user_input": user_input,
                        "response": "Configuration error: provider not properly configured",
                        "tool_calls": [],
                        "tool_details": [],
                        "messages": []
                    }

                langchain_provider = map_provider_to_langchain(agent_config.provider.name)
                llm = init_chat_model(
                    model=agent_config.model.name,
                    model_provider=langchain_provider,
                )

                agent = create_react_agent(
                    model=llm,
                    tools=limited_tools,
                    prompt=agent_config.instructions
                )

                log_student(f"DEBUG: Executing agent with LaunchDarkly max_tool_calls={max_tool_calls}, tools={len(tools)}")

                # Get the current message count before invoking
                prev_message_count = len(agent_messages)

                # Execute agent with natural recursion limits
                # Prefer async invoke if available
                if hasattr(agent, "ainvoke"):
                    response = await config_manager.track_metrics_async(
                        tracker,
                        lambda: agent.ainvoke(initial_state),
                        model_name=agent_config.model.name,
                        user_id=user_id,
                        user_context=user_context,
                        prev_message_count=prev_message_count
                    )
                else:
                    response = config_manager.track_metrics(
                        tracker,
                        lambda: agent.invoke(initial_state),
                        model_name=agent_config.model.name,
                        user_id=user_id,
                        user_context=user_context,
                        prev_message_count=prev_message_count
                    )

                # Update the response with our accurate tool count for LaunchDarkly metrics
                actual_tool_count = tool_counter["calls"]
                log_student(f"DEBUG: Agent completed - LaunchDarkly tool count: {actual_tool_count}/{max_tool_calls}")

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

                            # Extract search query from tool arguments
                            search_query = ""
                            
                            # Try direct query fields first
                            if 'query' in tool_args:
                                search_query = tool_args['query']
                            elif 'search_query' in tool_args:
                                search_query = tool_args['search_query']
                            elif 'q' in tool_args:
                                search_query = tool_args['q']
                            # Handle MCP tools with 'args' array containing dict with 'query'
                            elif 'args' in tool_args and isinstance(tool_args['args'], list) and len(tool_args['args']) > 0:
                                first_arg = tool_args['args'][0]
                                if isinstance(first_arg, dict) and 'query' in first_arg:
                                    search_query = first_arg['query']
                            # Handle nested kwargs structure
                            elif 'kwargs' in tool_args and isinstance(tool_args['kwargs'], dict):
                                search_query = tool_args['kwargs'].get('query', '')
                            
                            # Convert to string if needed
                            if search_query and not isinstance(search_query, str):
                                search_query = str(search_query)

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

        def invoke(self, request_data: dict) -> dict:
            """
            Synchronous wrapper that delegates to async path without using asyncio.run inside a running loop.
            """
            try:
                import asyncio as _asyncio
                try:
                    loop = _asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # Running inside an event loop; create a task and wait
                    return _asyncio.run(self.ainvoke(request_data))  # Fallback for environments without loop control
                else:
                    return _asyncio.run(self.ainvoke(request_data))
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