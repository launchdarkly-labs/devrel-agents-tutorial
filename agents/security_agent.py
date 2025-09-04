from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from config_manager import AgentConfig, FixedConfigManager as ConfigManager

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]
    # PII detection schema fields
    detected: bool
    types: List[str]
    redacted: str
    safe_to_proceed: bool

def create_security_agent(agent_config: AgentConfig, config_manager: ConfigManager):
    """Create security agent with PII detection tools"""
    
    # Create LangChain model from LDAI agent configuration
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    
    # Use provider.name from config instead of parsing model name
    provider_name = getattr(agent_config, 'provider', {}).get('name', '').lower()
    if provider_name == 'openai':
        model = ChatOpenAI(model=agent_config.model, temperature=agent_config.temperature)
    elif provider_name == 'anthropic':
        model = ChatAnthropic(model=agent_config.model, temperature=agent_config.temperature)
    else:
        # Fallback to Anthropic if provider not specified or unknown
        model = ChatAnthropic(model=agent_config.model, temperature=agent_config.temperature)
    
    tracker = agent_config.tracker
    
    # Create tools from LaunchDarkly configuration
    from tools_impl.dynamic_tool_factory import create_tools_from_launchdarkly
    tools = []
    if agent_config.tool_configs:
        # Mock AI config format for tool creation
        mock_ai_config = {
            "model": {
                "parameters": {
                    "tools": [
                        {"name": tool_name, "parameters": tool_config}
                        for tool_name, tool_config in agent_config.tool_configs.items()
                    ]
                }
            }
        }
        tools = create_tools_from_launchdarkly(mock_ai_config)
    
    print(f"🔐 CREATING SECURITY AGENT: Using LDAI model {agent_config.model} with {len(tools)} tools")
    
    # Store config values for nested functions
    config_instructions = agent_config.instructions
    
    def call_model_with_tools(state: AgentState):
        """Call the security model with PII detection tools"""
        try:
            messages = state["messages"]
            
            # Bind tools to model
            if tools:
                model_with_tools = model.bind_tools(tools)
            else:
                model_with_tools = model
            
            # Add system message with instructions if this is the first call
            if len(messages) == 1:  # Only user message
                system_prompt = config_instructions
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Track model call with LDAI metrics
            response = config_manager.track_metrics(
                tracker,
                lambda: model_with_tools.invoke(messages)
            )
            
            print(f"🔐 SECURITY MODEL RESPONSE: {len(response.content) if response.content else 0} chars")
            print(f"🔐 SECURITY TOOL CALLS: {len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0}")
            
            return {"messages": [response]}
            
        except Exception as e:
            print(f"❌ SECURITY ERROR: {e}")
            
            # Track error with LDAI metrics
            try:
                config_manager.track_metrics(
                    tracker,
                    lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
                )
            except:
                pass
            
            error_response = AIMessage(content="Security processing encountered an error.")
            return {"messages": [error_response]}
    
    def execute_tools(state: AgentState):
        """Execute any tools called by the security model"""
        try:
            messages = state["messages"]
            last_message = messages[-1]
            
            # Check if there are tool calls to execute
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                from langchain_core.messages import ToolMessage
                
                tool_results = []
                tool_calls_made = []
                tool_details = []
                
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    print(f"🔧 SECURITY TOOL CALLED: {tool_name} with args: {tool_args}")
                    
                    # Find the tool and execute it
                    tool_result = None
                    for tool in tools:
                        if hasattr(tool, 'name') and tool.name == tool_name:
                            tool_result = tool._run(**tool_args)
                            break
                    
                    if tool_result is None:
                        tool_result = f"Tool {tool_name} not found"
                    
                    print(f"🔧 SECURITY TOOL RESULT: {tool_name} -> {tool_result[:200]}...")
                    
                    # Create tool message
                    tool_message = ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_id
                    )
                    tool_results.append(tool_message)
                    tool_calls_made.append(tool_name)
                    
                    # Store tool details for UI
                    tool_details.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
                
                return {
                    "messages": tool_results,
                    "tool_calls": tool_calls_made,
                    "tool_details": tool_details
                }
            
            # No tools to execute
            return {"tool_calls": [], "tool_details": []}
            
        except Exception as e:
            print(f"❌ SECURITY TOOL ERROR: {e}")
            return {"tool_calls": [], "tool_details": []}
    
    def format_final_response(state: AgentState):
        """Format the final security agent response"""
        messages = state["messages"]
        
        # Get final response from last AI message
        final_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                final_message = message
                break
        
        if final_message:
            final_response = final_message.content
            if isinstance(final_response, list):
                text_parts = []
                for block in final_response:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                final_response = ' '.join(text_parts).strip()
        else:
            final_response = "Security processing completed."
        
        # Extract PII findings from tool results
        tool_calls_made = state.get("tool_calls", [])
        tool_details_from_execution = state.get("tool_details", [])
        
        # Default PII results (no PII detected)
        pii_results = {
            "detected": False,
            "types": [],
            "redacted": state.get("user_input", ""),
            "safe_to_proceed": True
        }
        
        # Look for PII detection tool results
        ui_tool_details = tool_details_from_execution.copy() if tool_details_from_execution else []
        
        for tool_detail in tool_details_from_execution:
            if tool_detail.get("name") == "pii_detection":
                try:
                    import json
                    result = json.loads(tool_detail.get("result", "{}"))
                    
                    # Use the exact schema results from the tool
                    pii_results = {
                        "detected": result.get("detected", False),
                        "types": result.get("types", []),
                        "redacted": result.get("redacted", state.get("user_input", "")),
                        "safe_to_proceed": result.get("safe_to_proceed", True)
                    }
                    
                    # Store for UI display
                    tool_detail["pii_result"] = pii_results
                        
                    print(f"🔍 PII TOOL RESULT: detected={pii_results['detected']}, types={pii_results['types']}, safe_to_proceed={pii_results['safe_to_proceed']}")
                    print(f"🔒 SECURITY CLEARANCE: {'PROCEED' if pii_results['safe_to_proceed'] else 'USE_REDACTED_TEXT'} - Text: '{pii_results['redacted'][:50]}...'")
                except Exception as e:
                    print(f"⚠️ PII tool result parsing error: {e}")
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls_made,
            "tool_details": ui_tool_details,
            "messages": messages,
            # Return the exact PII schema fields for supervisor and UI
            "detected": pii_results["detected"],
            "types": pii_results["types"], 
            "redacted": pii_results["redacted"],
            "safe_to_proceed": pii_results["safe_to_proceed"]
        }
    
    def should_continue(state: AgentState):
        """Determine if we should continue with tool execution or finish"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If the last message has tool calls, execute them
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        else:
            return "format"
    
    def call_model_again(state: AgentState):
        """Call model again after tool execution"""
        try:
            messages = state["messages"]
            
            # Track model call with LDAI metrics
            response = config_manager.track_metrics(
                tracker,
                lambda: model.invoke(messages)
            )
            
            print(f"🔐 SECURITY FOLLOW-UP RESPONSE: {len(response.content) if response.content else 0} chars")
            return {"messages": [response]}
            
        except Exception as e:
            print(f"❌ SECURITY FOLLOW-UP ERROR: {e}")
            error_response = AIMessage(content="Security follow-up processing encountered an error.")
            return {"messages": [error_response]}
    
    # Build workflow similar to support agent
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model_with_tools)
    workflow.add_node("tools", execute_tools)  
    workflow.add_node("agent_continue", call_model_again)
    workflow.add_node("format", format_final_response)
    
    workflow.set_entry_point("agent")
    
    # Conditional routing based on whether tools were called
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "format": "format"
        }
    )
    
    # After tools, call model again then format
    workflow.add_edge("tools", "agent_continue")  
    workflow.add_edge("agent_continue", "format")
    workflow.set_finish_point("format")
    
    return workflow.compile()