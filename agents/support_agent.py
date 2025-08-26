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

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]

def create_support_agent(config: AgentConfig):
    """Create a universal agent that works with any model provider"""
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    
    # Get MCP research tools asynchronously (MCP-only, no fallbacks)
    mcp_tool_map = {}
    try:
        # Try to get existing event loop, create new one if needed
        try:
            loop = asyncio.get_running_loop()
            # If we have a running loop, use create_task to run in background
            import concurrent.futures
            
            # Use thread pool executor to run MCP initialization in background
            with concurrent.futures.ThreadPoolExecutor() as executor:
                def sync_get_mcp_tools():
                    # Create a new event loop in this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(get_research_tools())
                    finally:
                        new_loop.close()
                
                future = executor.submit(sync_get_mcp_tools)
                mcp_tools = future.result(timeout=10)  # 10 second timeout
                print(f"DEBUG: Successfully loaded MCP tools in background thread")
                
        except RuntimeError:
            # No running loop, safe to create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mcp_tools = loop.run_until_complete(get_research_tools())
            loop.close()
        
        mcp_tool_map = {tool.name: tool for tool in mcp_tools}
        if mcp_tools:
            print(f"DEBUG: Loaded real MCP tools: {list(mcp_tool_map.keys())}")
        else:
            print("DEBUG: No MCP tools available - using basic tools only")
    except Exception as e:
        print(f"DEBUG: MCP initialization failed: {e}")
        mcp_tools = []
    
    for tool_name in config.allowed_tools:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
        elif tool_name == "arxiv_search":
            if "arxiv_search" in mcp_tool_map:
                available_tools.append(mcp_tool_map["arxiv_search"])
                print(f"DEBUG: Added real ArXiv MCP tool")
            else:
                print(f"DEBUG: ArXiv MCP tool requested but not available - install: npm install -g @michaellatman/mcp-server-arxiv")
        elif tool_name == "semantic_scholar":
            if "semantic_scholar" in mcp_tool_map:
                available_tools.append(mcp_tool_map["semantic_scholar"])
                print(f"DEBUG: Added real Semantic Scholar MCP tool")
            else:
                print(f"DEBUG: Semantic Scholar MCP tool requested but not available")
    
    # Initialize model based on LaunchDarkly config - support multiple providers
    model_name = config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=config.model, temperature=0.1)
    elif "claude" in model_name or "anthropic" in model_name:
        model = ChatAnthropic(model=config.model, temperature=0.1)
    else:
        # Default to Anthropic for unknown models
        model = ChatAnthropic(model=config.model, temperature=0.1)
    
    # Bind tools to model - this works universally across providers
    if available_tools:
        model = model.bind_tools(available_tools)
    
    # Create tool node for executing tools
    tool_node = ToolNode(available_tools)
    
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
                    recent_tool_calls.append(tool_call['name'])
        
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