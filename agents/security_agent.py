from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, SystemMessage
from config_manager import AgentConfig, FixedConfigManager as ConfigManager
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]  # Add support for detailed tool information with search queries

def create_security_agent(agent_config: AgentConfig, config_manager: ConfigManager):
    """Create security agent using LDAI SDK pattern"""
    
    # Create LangChain model from LDAI agent configuration
    # Create LangChain model directly from config
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    
    model_name = agent_config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=agent_config.model, temperature=agent_config.temperature)
    else:
        model = ChatAnthropic(model=agent_config.model, temperature=agent_config.temperature)
    tracker = agent_config.tracker
    
    print(f"🔐 CREATING SECURITY AGENT: Using LDAI model {agent_config.model}")
    
    # Store config values for nested functions
    config_instructions = agent_config.instructions
    config_temperature = agent_config.temperature
    
    # Initialize available tools (minimal for security - mostly native model capabilities)
    # Handle both old and new AgentConfig formats for compatibility
    tools_list = getattr(agent_config, 'allowed_tools', None) or getattr(agent_config, 'tools', [])
    if not tools_list:
        tools_list = []
    print(f"🔐 CREATING SECURITY AGENT: Starting with tools {tools_list}")
    
    available_tools = []
    
    # For security agent, we typically use fewer tools - focus on native model capabilities
    # But still support basic tools if configured from LaunchDarkly
    print(f"🔧 PROCESSING SECURITY TOOLS: {tools_list}")
    
    for tool_name in tools_list:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
    
    # Bind tools to model if available
    if available_tools:
        model = model.bind_tools(available_tools)
        
        def custom_tool_node(state: AgentState):
            """Custom tool execution with LDAI metrics tracking"""
            messages = state["messages"]
            last_message = messages[-1]
            
            # Only process if the last message has tool calls
            if not (hasattr(last_message, 'tool_calls') and last_message.tool_calls):
                return {"messages": []}
            
            tool_results = []
            
            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call.get('args', {})
                tool_id = tool_call.get('id', f"{tool_name}_{len(tool_results)}")
                
                print(f"🔧 SECURITY EXECUTING TOOL: {tool_name} with args: {tool_args}")
                
                # Find the tool by name
                tool_to_execute = None
                for tool in available_tools:
                    if hasattr(tool, 'name') and tool.name == tool_name:
                        tool_to_execute = tool
                        break
                
                if not tool_to_execute:
                    result = f"Error: Tool '{tool_name}' not found"
                else:
                    try:
                        # Pass recent search results to reranking tool by looking at message history
                        if tool_name == 'reranking':
                            # Find the most recent ToolMessage from search_v2 in conversation history
                            latest_search_message = None
                            for msg in reversed(messages):
                                if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
                                    # Check if this is a search_v2 tool result
                                    if ('search_v2' in str(msg.tool_call_id).lower() or 
                                        (hasattr(msg, 'content') and 'Found' in str(msg.content) and 'relevant document' in str(msg.content))):
                                        latest_search_message = msg
                                        break
                            
                            if latest_search_message:
                                # Pass the raw search_v2 output content to reranking tool
                                tool_args['results'] = latest_search_message.content
                            else:
                                # Fallback: no search_v2 results found
                                tool_args['results'] = ""
                        
                        # Execute the tool with LDAI metrics tracking
                        result = config_manager.track_metrics(
                            tracker,
                            lambda: tool_to_execute._run(**tool_args)
                        )
                        
                    except Exception as e:
                        result = f"Error executing {tool_name}: {str(e)}"
                        print(f"❌ SECURITY TOOL ERROR: {result}")
                        
                        # Track tool execution error with LDAI metrics
                        try:
                            config_manager.track_metrics(
                                tracker,
                                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
                            )
                        except:
                            pass
                
                # Create tool message
                tool_message = ToolMessage(content=str(result), tool_call_id=tool_id)
                tool_results.append(tool_message)
                
                print(f"🔧 SECURITY TOOL RESULT: {tool_name} -> {str(result)[:200]}...")
            
            return {"messages": tool_results}
        
        tool_node = custom_tool_node
        print(f"🔧 SECURITY TOOLS BOUND: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in available_tools]}")
    else:
        print(f"🔐 NO SECURITY TOOLS: Agent will work in model-only mode (preferred for security)")
        # Create empty tool node that won't be used
        def empty_tool_node(state: AgentState):
            return {"messages": []}
        tool_node = empty_tool_node
    
    def should_continue(state: AgentState):
        """Decide whether to continue with tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Count tool calls from all messages
        total_tool_calls = 0
        recent_tool_calls = []
        
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                total_tool_calls += len(message.tool_calls)
                for tool_call in message.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call.get('args', {})
                    recent_tool_calls.append(tool_name)
                    
                    # Extract search query from tool arguments
                    search_query = tool_args.get('query', '') or tool_args.get('search_query', '') or tool_args.get('q', '')
                    query_display = f"query: '{search_query}'" if search_query else "no query found"
                    
                    print(f"🔐 SECURITY TOOL CALLED: {tool_name} ({query_display})")
        
        # AGGRESSIVE: Stop tool loops immediately  
        if len(recent_tool_calls) >= 2:
            last_2_tools = recent_tool_calls[-2:]
            if len(set(last_2_tools)) == 1:  # Same tool used twice in a row
                print(f"🛑 SECURITY STOPPING TOOL LOOP: '{last_2_tools[0]}' used consecutively - ending")
                return "end"
        
        # Check max tool calls limit (conservative for security)
        max_tool_calls = 4  # Lower limit for security agent
        if total_tool_calls >= max_tool_calls:
            print(f"🛑 SECURITY MAX TOOL CALLS REACHED: {total_tool_calls}/{max_tool_calls}")
            return "end"
        
        # If model wants to use tools, continue
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        
        # Otherwise end
        return "end"
    
    def call_model(state: AgentState):
        """Call the security model with LDAI metrics tracking"""
        try:
            messages = state["messages"]
            
            # Add system message with instructions if this is the first call
            if len(messages) == 1:  # Only user message
                # Create detailed tool descriptions for the prompt
                tool_descriptions = []
                for tool in available_tools:
                    if hasattr(tool, 'name') and hasattr(tool, 'description'):
                        tool_descriptions.append(f"- {tool.name}: {tool.description}")
                
                tools_text = '\n'.join(tool_descriptions)
                system_prompt = f"""
                {config_instructions}
                
                Available tools:
                {tools_text}
                
                SECURITY FOCUS:
                - Use tools sparingly and only when necessary for security analysis
                - Focus on native model capabilities for PII detection and security tasks
                - Maximum 4 tool calls allowed for security agent
                """
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Track model call with LDAI metrics
            response = config_manager.track_metrics(
                tracker,
                lambda: model.invoke(messages)
            )
            
            return {"messages": [response]}
            
        except Exception as e:
            print(f"ERROR in security call_model: {e}")
            
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
    
    def format_final_response(state: AgentState):
        """Format the final security agent response with LDAI patterns"""
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
        
        # Extract all tool calls from the conversation with search queries
        tool_calls = []
        tool_details = []
        
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for call in message.tool_calls:
                    tool_name = call['name']
                    tool_args = call.get('args', {})
                    # Extract search query from tool arguments (check multiple possible field names)
                    search_query = (
                        tool_args.get('query', '') or 
                        tool_args.get('search_query', '') or 
                        tool_args.get('q', '') or
                        tool_args.get('results', '') or
                        tool_args.get('text', '')
                    )
                    
                    # Always append tool name as string for API compatibility
                    tool_calls.append(tool_name)
                    
                    # Also store detailed info with search query for UI
                    tool_detail = {
                        "name": tool_name,
                        "search_query": search_query if search_query else None,
                        "args": tool_args
                    }
                    tool_details.append(tool_detail)
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls,
            "tool_details": tool_details,
            "messages": messages
        }
    
    # Build workflow with conditional tool support
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("format", format_final_response)
    
    # Add tool node
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": "format"
        }
    )
    
    # After tools, go back to agent (for multi-turn)
    workflow.add_edge("tools", "agent")
    
    workflow.set_finish_point("format")
    
    return workflow.compile()