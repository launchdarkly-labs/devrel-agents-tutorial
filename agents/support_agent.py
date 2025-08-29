from typing import TypedDict, List, Annotated
from typing_extensions import Annotated as TypingAnnotated
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool
from tools_impl.mcp_research_tools import get_research_tools
import asyncio
from policy.config_manager import AgentConfig

# Simplified approach - no caching for demo clarity

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]  # Add support for detailed tool information with search queries

def create_support_agent(config: AgentConfig):
    """Create a universal agent that works with any model provider"""
    print(f"🏗️  CREATING SUPPORT AGENT: Starting with tools {config.allowed_tools}")
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    
    # Load MCP tools using improved initialization
    print("🔄 LOADING MCP TOOLS: Connecting to MCP servers...")
    mcp_tool_map = {}
    
    try:
        # Get MCP tools using the research tools module
        print("DEBUG: get_research_tools called")
        print("DEBUG: Getting MCP research tools instance")
        
        # Initialize MCP research tools in background thread to avoid async conflicts
        import concurrent.futures
        import threading
        
        def initialize_mcp_tools():
            """Initialize MCP tools in a separate thread with new event loop"""
            try:
                # Create fresh event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                print("DEBUG: Creating new MCPResearchTools instance")
                from tools_impl.mcp_research_tools import MCPResearchTools
                mcp_client = MCPResearchTools()
                
                print("DEBUG: Initializing MCP tools...")
                result = loop.run_until_complete(mcp_client.initialize())
                
                # Get available MCP tools
                available_mcp_tools = []
                if hasattr(mcp_client, 'tools') and mcp_client.tools:
                    for tool_name, tool_instance in mcp_client.tools.items():
                        available_mcp_tools.append(tool_instance)
                        print(f"DEBUG: Found MCP tool: {tool_name} ({tool_instance.description[:50]}...)")
                
                print(f"DEBUG: Initialized MCP tools: {[tool.name for tool in available_mcp_tools]}")
                return available_mcp_tools
                
            except Exception as e:
                print(f"DEBUG: MCP initialization error: {e}")
                return []
            finally:
                try:
                    loop.close()
                except:
                    pass
        
        # Run MCP initialization in thread with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(initialize_mcp_tools)
            try:
                mcp_tools = future.result(timeout=10)  # 10 second timeout
                print("DEBUG: MCP initialization completed")
                
                # Create tool map
                mcp_tool_map = {tool.name: tool for tool in mcp_tools if hasattr(tool, 'name')}
                print(f"DEBUG: Available MCP tools: {list(mcp_tool_map.keys())}")
                
                if mcp_tools:
                    # Map common tools for easy access
                    for tool in mcp_tools:
                        if hasattr(tool, 'name'):
                            if 'arxiv' in tool.name.lower() or 'search_papers' in tool.name:
                                print("✅ Added ArXiv MCP tool")
                            elif 'semantic' in tool.name.lower() or 'scholar' in tool.name.lower():
                                print("✅ Added Semantic Scholar MCP tool")
                    
                    print("DEBUG: Returning {} MCP tools".format(len(mcp_tools)))
                    print(f"✅ MCP TOOLS LOADED: {list(mcp_tool_map.keys())}")
                else:
                    print("📚 NO MCP TOOLS: Using internal tools only")
                    
            except concurrent.futures.TimeoutError:
                print("⏰ MCP TIMEOUT: MCP servers not responding - using internal tools only")
                mcp_tool_map = {}
                
    except Exception as e:
        print(f"❌ MCP ERROR: {e} - Using internal tools only")
        mcp_tool_map = {}
    
    # Map LaunchDarkly tool names to actual MCP tool names
    ld_to_mcp_mapping = {
        "arxiv_search": "search_papers", 
        "semantic_scholar": "search_semantic_scholar"
    }
    
    print(f"🔧 PROCESSING TOOLS: {config.allowed_tools}")
    print(f"🗺️  MCP TOOL MAP KEYS: {list(mcp_tool_map.keys())}")
    
    for tool_name in config.allowed_tools:
        print(f"⚙️  Processing tool: {tool_name}")
        
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
            print(f"📚 INTERNAL TOOL ADDED: Basic vector search (search_v1)")
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
            print(f"📚 INTERNAL TOOL ADDED: Advanced vector search with embeddings (search_v2)")
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
            print(f"📊 INTERNAL TOOL ADDED: BM25 reranking algorithm (reranking)")
        elif tool_name in ["arxiv_search", "semantic_scholar"]:
            # Use mapping to find the actual MCP tool
            mcp_tool_name = ld_to_mcp_mapping.get(tool_name)
            if mcp_tool_name and mcp_tool_name in mcp_tool_map:
                # Create a proper wrapper that inherits from BaseTool
                mcp_tool = mcp_tool_map[mcp_tool_name]
                
                from langchain.tools import BaseTool
                from typing import Any
                import json
                
                class MCPToolWrapper(BaseTool):
                    name: str = tool_name  # Use LaunchDarkly name
                    description: str = mcp_tool.description
                    wrapped_tool: Any = None  # Declare as Pydantic field
                    
                    def __init__(self, mcp_tool, ld_name):
                        super().__init__()
                        object.__setattr__(self, 'wrapped_tool', mcp_tool)
                        object.__setattr__(self, 'name', ld_name)
                    
                    def _run(self, **kwargs) -> str:
                        """Execute the wrapped MCP tool"""
                        try:
                            # Remove config if it exists (LangChain passes this but MCP tools don't need it)
                            tool_kwargs = {k: v for k, v in kwargs.items() if k != 'config'}
                            
                            # Call the MCP tool directly
                            if hasattr(self.wrapped_tool, '_run'):
                                result = self.wrapped_tool._run(**tool_kwargs)
                            elif hasattr(self.wrapped_tool, 'invoke'):
                                result = self.wrapped_tool.invoke(tool_kwargs)
                            else:
                                # Fallback: try to call the tool directly
                                result = self.wrapped_tool(**tool_kwargs)
                            
                            if isinstance(result, dict):
                                return json.dumps(result, indent=2)
                            elif isinstance(result, list):
                                return json.dumps(result, indent=2)
                            else:
                                return str(result)
                        except Exception as e:
                            print(f"❌ MCP TOOL ERROR: {e}")
                            return f"MCP tool error: {str(e)}"
                
                wrapped_mcp_tool = MCPToolWrapper(mcp_tool, tool_name)
                available_tools.append(wrapped_mcp_tool)
                print(f"🔬 MCP TOOL ADDED (WRAPPED): {tool_name} -> {mcp_tool_name} via MCP server")
            else:
                print(f"❌ MCP TOOL UNAVAILABLE: {tool_name} requested but not in map {list(mcp_tool_map.keys())} - SKIPPING")
        else:
            print(f"❓ UNKNOWN TOOL REQUESTED: {tool_name} - SKIPPING")
    
    # Initialize model based on LaunchDarkly config - support multiple providers
    model_name = config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=config.model, temperature=config.temperature)
    elif "claude" in model_name or "anthropic" in model_name:
        model = ChatAnthropic(model=config.model, temperature=config.temperature)
    else:
        # Default to Anthropic for unknown models
        model = ChatAnthropic(model=config.model, temperature=config.temperature)
    
    # Debug: Show final available tools
    print(f"🔧 FINAL AVAILABLE TOOLS: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in available_tools]}")
    
    # Bind tools to model - this works universally across providers
    if available_tools:
        model = model.bind_tools(available_tools)
        # Create tool node for executing tools
        tool_node = ToolNode(available_tools)
    else:
        print(f"⚠️  NO TOOLS AVAILABLE: Agent will work in model-only mode")
        # Create empty tool node that won't be used
        tool_node = None
    
    def should_continue(state: AgentState):
        """Decide whether to continue with tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Count tool calls from all messages in the conversation
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
                    
                    # Log tool usage type with search terms
                    if tool_name in ['search_papers', 'search_semantic_scholar']:
                        print(f"🔬 MCP TOOL CALLED: {tool_name} ({query_display}) (external research server)")
                    elif tool_name in ['search_v1', 'search_v2', 'reranking']:
                        print(f"📚 INTERNAL TOOL CALLED: {tool_name} ({query_display}) (local processing)")
                    else:
                        print(f"🔧 UNKNOWN TOOL CALLED: {tool_name} ({query_display})")
        
        # Check for consecutive identical tool calls (limit: 3 in a row, but give one more chance to finish)
        consecutive_limit = 3
        if len(recent_tool_calls) >= consecutive_limit:
            last_tools = recent_tool_calls[-consecutive_limit:]
            if len(set(last_tools)) == 1:  # All the same tool
                print(f"DEBUG: Too many consecutive uses of {last_tools[0]} ({consecutive_limit} times), but allowing final response")
                # Don't end immediately - let the model provide a final response
                # We'll check this in call_model and force a final response
                pass
        
        print(f"DEBUG: should_continue - total_tool_calls: {total_tool_calls}, max: {config.max_tool_calls}")
        print(f"DEBUG: Recent tool calls: {recent_tool_calls[-5:]}")  # Show last 5
        
        # If we've hit the max tool calls limit, end
        if total_tool_calls >= config.max_tool_calls:
            print("DEBUG: Hit max tool calls limit, ending")
            return "end"
        
        # If the last message has tool calls, continue to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            print(f"DEBUG: Last message has {len(last_message.tool_calls)} tool calls, continuing to tools")
            return "tools"
        
        # Otherwise, we're done
        print("DEBUG: No more tool calls needed, ending")
        return "end"
    
    def call_model(state: AgentState):
        """Call the model with the current conversation state"""
        try:
            messages = state["messages"]
            
            # Count tool calls from all messages in the conversation
            total_tool_calls = 0
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    total_tool_calls += len(message.tool_calls)
            
            print(f"DEBUG: call_model - total_tool_calls: {total_tool_calls}, messages: {len(messages)}")
            
            # Add system message with instructions if this is the first call
            if len(messages) == 1:  # Only user message
                system_prompt = f"""
                {config.instructions}
                
                Available tools: {[tool.name for tool in available_tools]}
                
                You can use tools to help answer questions. Use as many tools as needed (max {config.max_tool_calls}), but be efficient.
                When you have enough information, provide your final answer without using more tools.
                """
                messages = [HumanMessage(content=system_prompt)] + messages
            
            # Check for consecutive tool usage or approaching limit
            recent_tool_calls = []
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        recent_tool_calls.append(tool_call['name'])
            
            # Force final response if we've used too many tools or hit consecutive limit
            force_final_response = False
            if total_tool_calls >= config.max_tool_calls - 1:
                force_final_response = True
            elif len(recent_tool_calls) >= 3:
                last_3_tools = recent_tool_calls[-3:]
                if len(set(last_3_tools)) == 1:  # Same tool used 3 times
                    force_final_response = True
            
            if force_final_response:
                wrap_up_prompt = HumanMessage(content=f"""
                You've used {total_tool_calls} tools so far (recent: {recent_tool_calls[-5:]}). 
                
                Please provide your final comprehensive answer based on all the information you've gathered. 
                
                Make sure to:
                1. Answer the original Q-learning question thoroughly
                2. Provide a complete response
                
                Do NOT use any more tools - just give your final answer.
                """)
                messages = messages + [wrap_up_prompt]
            
            response = model.invoke(messages)
            print(f"DEBUG: Model response received, has_tool_calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")
            return {"messages": [response]}
        except Exception as e:
            print(f"ERROR in call_model: {e}")
            error_response = AIMessage(content="I apologize, but I encountered an error processing your request.")
            return {"messages": [error_response]}
    
    def format_final_response(state: AgentState):
        """Format the final response and extract tool usage"""
        messages = state["messages"]
        tool_calls = []
        tool_details = []
        
        # Create mapping from MCP tool names back to LaunchDarkly names for UI display
        mcp_to_ld_mapping = {
            "search_papers": "arxiv_search",
            "search_semantic_scholar": "semantic_scholar"
        }
        
        # Extract all tool calls from the conversation with search queries
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for call in message.tool_calls:
                    actual_tool_name = call['name']
                    tool_args = call.get('args', {})
                    # Extract search query from tool arguments (check multiple possible field names)
                    # Also check nested kwargs structure used by MCP tools
                    search_query = (
                        tool_args.get('query', '') or 
                        tool_args.get('search_query', '') or 
                        tool_args.get('q', '') or
                        tool_args.get('results', '') or
                        tool_args.get('text', '') or
                        (tool_args.get('kwargs', {}).get('query', '') if isinstance(tool_args.get('kwargs'), dict) else '')
                    )
                    
                    # Map MCP tool name back to LaunchDarkly name for UI display
                    display_tool_name = mcp_to_ld_mapping.get(actual_tool_name, actual_tool_name)
                    
                    # Debug: Log search query extraction
                    if search_query:
                        print(f"🔍 EXTRACTED SEARCH QUERY: {display_tool_name} -> '{search_query}'")
                    else:
                        print(f"⚠️  NO SEARCH QUERY: {display_tool_name} (args: {list(tool_args.keys())})")
                    
                    # Always append tool name as string for API compatibility
                    tool_calls.append(display_tool_name)
                    
                    # Also store detailed info with search query for UI
                    tool_detail = {
                        "name": display_tool_name,
                        "search_query": search_query if search_query else None,
                        "args": tool_args
                    }
                    tool_details.append(tool_detail)
        
        # Get the final assistant message
        final_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                final_message = message
                break
        
        if final_message:
            final_response = final_message.content
            
            # Handle different response content types from Claude
            if isinstance(final_response, list):
                # Extract text from Claude's complex response format
                text_parts = []
                for block in final_response:
                    if isinstance(block, dict):
                        if block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                    elif isinstance(block, str):
                        text_parts.append(block)
                final_response = ' '.join(text_parts).strip()
            
            if not final_response:
                final_response = "I apologize, but I couldn't generate a proper response."
        else:
            final_response = "I apologize, but I couldn't generate a proper response."
        
        print(f"🔧 SUPPORT AGENT RETURNING:")
        print(f"   📊 tool_calls: {tool_calls}")
        print(f"   📊 tool_details: {tool_details}")
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls,
            "tool_details": tool_details,
            "messages": messages
        }
    
    # Build the workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.add_node("format", format_final_response)
    
    # Set entry point
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
    
    # Format is the final step
    workflow.set_finish_point("format")
    
    return workflow.compile()