from typing import TypedDict, List, Annotated, Optional
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

def get_model_instance(model_name: str, temperature: float):
    """Get a model instance without tools bound"""
    if "gpt" in model_name.lower():
        return ChatOpenAI(model=model_name, temperature=temperature)
    else:
        # Default to Anthropic for unknown models
        return ChatAnthropic(model=model_name, temperature=temperature)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]  # Add support for detailed tool information with search queries
    most_recent_search_results: Optional[str]  # Store the most recent search results for reranking
    most_recent_query: Optional[str]  # Store the most recent search query

def create_support_agent(config: AgentConfig, config_manager=None):
    """Create a universal agent that works with any model provider"""
    # Handle both old and new AgentConfig formats for compatibility
    tools_list = getattr(config, 'allowed_tools', None) or getattr(config, 'tools', [])
    print(f"🏗️  CREATING SUPPORT AGENT: Starting with tools {tools_list}")
    
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
                mcp_tools = future.result(timeout=30)  # 30 second timeout
                
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
    
    print(f"🔧 PROCESSING TOOLS: {tools_list}")
    print(f"🗺️  MCP TOOL MAP KEYS: {list(mcp_tool_map.keys())}")
    
    for tool_name in tools_list:
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
                    
                    def _run(self, config=None, **kwargs) -> str:
                        """Execute the wrapped MCP tool"""
                        try:
                            # Call the MCP tool directly (ignore config parameter)
                            if hasattr(self.wrapped_tool, '_run'):
                                result = self.wrapped_tool._run(**kwargs)
                            elif hasattr(self.wrapped_tool, 'invoke'):
                                result = self.wrapped_tool.invoke(kwargs)
                            else:
                                # Fallback: try to call the tool directly
                                result = self.wrapped_tool(**kwargs)
                            
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
    # Handle both old and new AgentConfig formats
    model_name_attr = getattr(config, 'model', None) or getattr(config, 'model_name', 'claude-3-haiku-20240307')
    model_name = model_name_attr.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=model_name_attr, temperature=config.temperature)
    elif "claude" in model_name or "anthropic" in model_name:
        model = ChatAnthropic(model=model_name_attr, temperature=config.temperature)
    else:
        # Default to Anthropic for unknown models
        model = ChatAnthropic(model=model_name_attr, temperature=config.temperature)
    
    # Debug: Show final available tools
    print(f"🔧 FINAL AVAILABLE TOOLS: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in available_tools]}")
    
    # Store config values for nested functions
    config_instructions = config.instructions
    config_temperature = config.temperature
    
    # Bind tools to model - this works universally across providers
    if available_tools:
        model = model.bind_tools(available_tools)
        
        # Create CUSTOM tool node that passes conversation context
        def custom_tool_node(state: AgentState):
            """Custom tool execution that passes conversation context to tools"""
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
                
                print(f"🔧 EXECUTING TOOL: {tool_name} with args: {tool_args}")
                
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
                        
                        # For MCP tools, ensure config parameter is handled
                        if tool_name in ['arxiv_search', 'semantic_scholar']:
                            # MCP tools expect config parameter
                            if 'config' not in tool_args:
                                tool_args['config'] = None
                        
                        # Execute the tool
                        result = tool_to_execute._run(**tool_args)
                    except Exception as e:
                        result = f"Error executing {tool_name}: {str(e)}"
                        print(f"❌ TOOL ERROR: {result}")
                
                # Create tool message
                tool_message = ToolMessage(content=str(result), tool_call_id=tool_id)
                tool_results.append(tool_message)
                
                print(f"🔧 TOOL RESULT: {tool_name} -> {str(result)[:200]}...")
            
            return {"messages": tool_results}
        
        tool_node = custom_tool_node
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
        
        # AGGRESSIVE: Stop tool loops immediately
        if len(recent_tool_calls) >= 2:
            last_2_tools = recent_tool_calls[-2:]
            if len(set(last_2_tools)) == 1:  # Same tool used twice in a row
                print(f"🛑 STOPPING TOOL LOOP: '{last_2_tools[0]}' used consecutively - ending workflow")
                return "end"
        
        print(f"DEBUG: should_continue - total_tool_calls: {total_tool_calls}, max: 10")
        print(f"DEBUG: Recent tool calls: {recent_tool_calls[-5:]}")  # Show last 5
        
        # If we've hit the max tool calls limit, end
        if total_tool_calls >= 10:
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
                
                TOOL USAGE GUIDELINES:
                - Be strategic and efficient with tool usage
                - Use different tools to gather complementary information
                - Avoid repeating the same tool unnecessarily
                - When you have sufficient information, provide your answer
                - Maximum 10 tool calls allowed
                """
                messages = [HumanMessage(content=system_prompt)] + messages
            
            # Simple and effective: Check for tool overuse and REMOVE tools if needed
            recent_tool_calls = []
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        recent_tool_calls.append(tool_call['name'])
            
            # STRICT tool limits - force completion
            should_disable_tools = False
            
            # If approaching max tool calls, disable tools
            if total_tool_calls >= 9:
                should_disable_tools = True
                print(f"🛑 DISABLING TOOLS: Reached max tools ({total_tool_calls}/10)")
            
            # If repeating the same tool too much, disable tools
            elif len(recent_tool_calls) >= 2:
                last_2_tools = recent_tool_calls[-2:]
                if len(set(last_2_tools)) == 1:  # Same tool used twice in a row
                    should_disable_tools = True
                    print(f"🛑 DISABLING TOOLS: Repeated tool '{last_2_tools[0]}' - forcing completion")
            
            # Actually disable tools by creating a model without tools
            if should_disable_tools:
                # Use the base model without any tools bound
                model_name_for_completion = getattr(config, 'model', None) or getattr(config, 'model_name', 'claude-3-haiku-20240307')
                completion_model = get_model_instance(model_name_for_completion, config_temperature)
                response = completion_model.invoke(messages)
                print(f"🎯 FORCED COMPLETION: Model response without tools")
                return {"messages": [response]}
            
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