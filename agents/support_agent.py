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

def create_support_agent(config: AgentConfig):
    """Create a universal agent that works with any model provider"""
    print(f"🏗️  CREATING SUPPORT AGENT: Starting with tools {config.allowed_tools}")
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    
    # Simple MCP tool loading - no caching for demo clarity
    print("🔄 LOADING MCP TOOLS: Connecting to MCP servers...")
    mcp_tool_map = {}
    
    try:
        import concurrent.futures
        
        def load_mcp_tools():
            # Create new event loop for MCP initialization
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(get_research_tools())
            finally:
                new_loop.close()
        
        # Load MCP tools with timeout
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(load_mcp_tools)
            try:
                mcp_tools = future.result(timeout=5)  # 5 second timeout
                mcp_tool_map = {tool.name: tool for tool in mcp_tools}
                
                if mcp_tools:
                    print(f"✅ MCP TOOLS LOADED: {list(mcp_tool_map.keys())}")
                else:
                    print("📚 NO MCP TOOLS: Using internal tools only")
            except concurrent.futures.TimeoutError:
                print("⏰ MCP TIMEOUT: MCP servers not responding - using internal tools only")
                mcp_tool_map = {}
                
    except Exception as e:
        print(f"❌ MCP ERROR: {e} - Using internal tools only")
        mcp_tool_map = {}
    
    for tool_name in config.allowed_tools:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
            print(f"📚 INTERNAL TOOL: Basic vector search (search_v1)")
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
            print(f"📚 INTERNAL TOOL: Advanced vector search with embeddings (search_v2)")
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
            print(f"📊 INTERNAL TOOL: BM25 reranking algorithm (reranking)")
        elif tool_name == "arxiv_search":
            if "search_papers" in mcp_tool_map:
                available_tools.append(mcp_tool_map["search_papers"])
                print(f"🔬 MCP TOOL ENABLED: ArXiv research via real MCP server (search_papers)")
            else:
                print(f"❌ MCP TOOL UNAVAILABLE: ArXiv MCP tool requested but search_papers not available - SKIPPING")
                # Skip this tool - don't add anything to available_tools
        elif tool_name == "semantic_scholar":
            if "search_semantic_scholar" in mcp_tool_map:
                available_tools.append(mcp_tool_map["search_semantic_scholar"])
                print(f"🔬 MCP TOOL ENABLED: Semantic Scholar via real MCP server (search_semantic_scholar)")
            else:
                print(f"❌ MCP TOOL UNAVAILABLE: Semantic Scholar MCP tool requested but search_semantic_scholar not available - SKIPPING")
                # Skip this tool - don't add anything to available_tools
        else:
            print(f"❓ UNKNOWN TOOL REQUESTED: {tool_name} - SKIPPING")
    
    # Initialize model based on LaunchDarkly config - support multiple providers
    model_name = config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=config.model, temperature=0.1)
    elif "claude" in model_name or "anthropic" in model_name:
        model = ChatAnthropic(model=config.model, temperature=0.1)
    else:
        # Default to Anthropic for unknown models
        model = ChatAnthropic(model=config.model, temperature=0.1)
    
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
                2. Handle any PII redaction if needed (like email addresses or phone numbers)
                3. Provide a complete response
                
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
        
        # Extract all tool calls from the conversation
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_calls.extend([call['name'] for call in message.tool_calls])
        
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
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls,
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