from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from policy.config_manager import AgentConfig, ConfigManager
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]

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
    
    # Initialize available tools (minimal for security - mostly native model capabilities)
    available_tools = []
    
    # For security agent, we typically use fewer tools - focus on native model capabilities
    # But still support basic tools if configured
    basic_tools = ["search_v1", "search_v2", "reranking"]
    
    for tool_name in basic_tools:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
            print(f"🔍 SECURITY TOOL LOADED: {tool_name} (basic search)")
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
            print(f"🔍 SECURITY TOOL LOADED: {tool_name} (vector search)")
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
            print(f"🔍 SECURITY TOOL LOADED: {tool_name} (semantic reranking)")
    
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
                        # PASS CONVERSATION CONTEXT to tools (especially reranking)
                        if tool_name == 'reranking':
                            # For reranking tool, pass conversation content as simple strings
                            message_contents = []
                            for msg in messages:
                                try:
                                    # Extract just the content as plain string
                                    if hasattr(msg, 'content') and msg.content:
                                        content = str(msg.content)
                                        if content.strip():  # Only include non-empty content
                                            message_contents.append(content)
                                except Exception as e:
                                    print(f"   ⚠️ Error extracting message content: {e}")
                                    continue
                            
                            # Pass as simple list of strings - completely JSON serializable
                            tool_args['message_contents'] = message_contents
                        
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
        tool_node = None
    
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
            
            # Add system message if first call
            if len(messages) == 1:
                messages = [HumanMessage(content=agent_config.instructions)] + messages
            
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
        
        # Extract tool calls from messages
        tool_calls = []
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call.get('args', {})
                    # Extract search query for display
                    search_query = tool_args.get('query', '') or tool_args.get('search_query', '') or tool_args.get('q', '')
                    tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "search_query": search_query
                    })
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls,
            "messages": messages
        }
    
    # Build workflow with conditional tool support
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("format", format_final_response)
    
    # Add tool node if tools are available
    if tool_node:
        workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    # Add conditional edges based on tool availability
    if tool_node:
        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": "format"})
        workflow.add_edge("tools", "agent")
    else:
        workflow.add_conditional_edges("agent", should_continue, {"end": "format"})
    
    workflow.set_finish_point("format")
    
    return workflow.compile()