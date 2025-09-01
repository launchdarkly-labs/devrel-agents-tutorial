from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode  
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool
from tools_impl.mcp_runtime import MCPRuntime
from policy.config_manager import AgentConfig

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]

def create_support_agent(config: AgentConfig, config_manager=None):
    """Create a simple support agent that works with new AgentConfig format"""
    print(f"🏗️  CREATING SIMPLE SUPPORT AGENT: Starting with tools {config.tools}")
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    
    # Add internal tools
    for tool_name in (config.tools or []):
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
            print(f"📚 Added search_v1")
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
            print(f"📚 Added search_v2")
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
            print(f"📊 Added reranking")
        elif tool_name in ["arxiv_search", "semantic_scholar"]:
            # Add MCP tools using singleton
            try:
                runtime = MCPRuntime.get_instance()
                if tool_name == "arxiv_search" and "search_papers" in runtime.tools:
                    available_tools.append(runtime.tools["search_papers"])
                    print(f"🔬 Added MCP arxiv_search")
                elif tool_name == "semantic_scholar" and "search_semantic_scholar" in runtime.tools:
                    available_tools.append(runtime.tools["search_semantic_scholar"])
                    print(f"🔬 Added MCP semantic_scholar")
            except Exception as e:
                print(f"⚠️ MCP tool {tool_name} unavailable: {e}")
    
    print(f"✅ Final tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in available_tools]}")
    
    # Create model using config manager if available
    if config_manager:
        model = config_manager.create_langchain_model(config)
        print(f"✅ Model created via config_manager: {config.model_name}")
    else:
        # Fallback model creation
        from langchain_anthropic import ChatAnthropic
        model = ChatAnthropic(model=config.model_name, temperature=config.temperature)
        print(f"✅ Fallback model created: {config.model_name}")
    
    # Bind tools if available
    if available_tools:
        model = model.bind_tools(available_tools)
        tool_node = ToolNode(available_tools)
        print(f"🛠️  Bound {len(available_tools)} tools to model")
    else:
        tool_node = None
        print("⚠️ No tools available")
    
    def should_continue(state: AgentState):
        """Simple continuation logic"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Count total tool calls
        total_calls = sum(len(msg.tool_calls) if hasattr(msg, 'tool_calls') and msg.tool_calls else 0 
                         for msg in messages)
        
        if total_calls >= 10:
            print(f"🛑 Max tool calls reached: {total_calls}")
            return "end"
            
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        else:
            return "end"
    
    def call_model(state: AgentState):
        """Call model with LaunchDarkly metrics tracking"""
        messages = state["messages"]
        
        # Add system message on first call
        if len(messages) == 1:
            system_msg = HumanMessage(content=f"""
            {config.instructions}
            
            You have access to these tools: {[tool.name for tool in available_tools]}
            Use them strategically to help the user.
            """)
            messages = [system_msg] + messages
        
        # Track with LaunchDarkly metrics if available
        if config.tracker:
            print("📊 Tracking model call with LaunchDarkly metrics")
            response = config_manager.track_metrics(config.tracker, lambda: model.invoke(messages))
        else:
            response = model.invoke(messages)
            
        return {"messages": [response]}
    
    # Build workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    
    if tool_node:
        workflow.add_node("tools", tool_node)
        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": "end"})
        workflow.add_edge("tools", "agent")
    else:
        workflow.add_conditional_edges("agent", should_continue, {"end": "end"})
    
    workflow.set_entry_point("agent")
    graph = workflow.compile()
    
    print("✅ Simple support agent created successfully")
    return graph