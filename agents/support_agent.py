from typing import TypedDict, List, Annotated, Optional
from typing_extensions import Annotated as TypingAnnotated
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool
from tools_impl.mcp_research_tools import get_research_tools
from utils.logger import log_student, log_debug, log_verbose
import asyncio

# Simplified approach - no caching for demo clarity

def get_model_instance(model_name: str, temperature: float, provider_name: str = None):
    """Get a model instance using LDAI SDK pattern"""
    from langchain.chat_models import init_chat_model
    from config_manager import map_provider_to_langchain
    
    if provider_name:
        langchain_provider = map_provider_to_langchain(provider_name)
    else:
        # Fallback: infer provider from model name  
        if "gpt" in model_name.lower():
            langchain_provider = "openai"
        else:
            langchain_provider = "anthropic"
    
    return init_chat_model(
        model=model_name,
        model_provider=langchain_provider,
        temperature=temperature
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]  # Add support for detailed tool information with search queries

def create_support_agent(config, config_manager=None):
    """Create a universal agent that works with any model provider"""
    # Extract tools from LaunchDarkly AI Config
    tools_list = []
    tool_configs = {}
    max_tool_calls = 8  # default
    
    # Try to get tools from AI config
    if hasattr(config, 'tools') and config.tools:
        tools_list = list(config.tools)
    
    # Try to get tool configurations and custom parameters
    try:
        config_dict = config.to_dict()
        if 'model' in config_dict and 'parameters' in config_dict['model'] and 'tools' in config_dict['model']['parameters']:
            tools_data = config_dict['model']['parameters']['tools']
            for tool in tools_data:
                if 'name' in tool:
                    tool_name = tool['name']
                    if tool_name not in tools_list:
                        tools_list.append(tool_name)
                    tool_configs[tool_name] = tool.get('parameters', {})
        
        # Extract max_tool_calls from customParameters
        if 'customParameters' in config_dict and config_dict['customParameters']:
            custom_params = config_dict['customParameters']
            if 'max_tool_calls' in custom_params:
                max_tool_calls = custom_params['max_tool_calls']
        elif 'model' in config_dict and 'custom' in config_dict['model'] and config_dict['model']['custom']:
            custom_params = config_dict['model']['custom']
            if 'max_tool_calls' in custom_params:
                max_tool_calls = custom_params['max_tool_calls']
    except Exception:
        pass  # Fallback to just the tools list and defaults
    if not tools_list:
        tools_list = []
    log_debug(f"🏗️  CREATING SUPPORT AGENT: Starting with tools {tools_list}")
    if tool_configs:
        log_verbose(f"🔧 TOOL CONFIGS FROM LAUNCHDARKLY: {tool_configs}")
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    
    # Load MCP tools using improved initialization
    log_debug("🔄 LOADING MCP TOOLS: Connecting to MCP servers...")
    mcp_tool_map = {}
    
    # Only load MCP tools if they're requested in allowed_tools
    mcp_tools_requested = any(tool in tools_list for tool in ['arxiv_search', 'semantic_scholar', 'search_papers', 'search_semantic_scholar'])
    
    if mcp_tools_requested:
        try:
            # Get MCP tools using the research tools module
            # print("DEBUG: get_research_tools called")
            # print("DEBUG: Getting MCP research tools instance")
            
            # Initialize MCP research tools in background thread to avoid async conflicts
            import concurrent.futures
            import threading
            
            def initialize_mcp_tools():
                """Initialize MCP tools in a separate thread with new event loop"""
                try:
                    # Create fresh event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # print("DEBUG: Creating new MCPResearchTools instance")
                    from tools_impl.mcp_research_tools import MCPResearchTools
                    mcp_client = MCPResearchTools()
                    
                    # print("DEBUG: Initializing MCP tools...")
                    result = loop.run_until_complete(mcp_client.initialize())
                    
                    # Get available MCP tools
                    available_mcp_tools = []
                    if hasattr(mcp_client, 'tools') and mcp_client.tools:
                        for tool_name, tool_instance in mcp_client.tools.items():
                            available_mcp_tools.append(tool_instance)
                            # print(f"DEBUG: Found MCP tool: {tool_name} ({tool_instance.description[:50]}...)")
                    
                    # print(f"DEBUG: Initialized MCP tools: {[tool.name for tool in available_mcp_tools]}")
                    return available_mcp_tools
                    
                except Exception as e:
                    # print(f"DEBUG: MCP initialization error: {e}")
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
                    # print(f"DEBUG: Available MCP tools: {list(mcp_tool_map.keys())}")
                    
                    if mcp_tools:
                        # Map common tools for easy access
                        for tool in mcp_tools:
                            if hasattr(tool, 'name'):
                                if 'arxiv' in tool.name.lower() or 'search_papers' in tool.name:
                                    print("✅ Added ArXiv MCP tool")
                                elif 'semantic' in tool.name.lower() or 'scholar' in tool.name.lower():
                                    print("✅ Added Semantic Scholar MCP tool")
                        
                        # print("DEBUG: Returning {} MCP tools".format(len(mcp_tools)))
                        print(f"✅ MCP TOOLS LOADED: {list(mcp_tool_map.keys())}")
                    else:
                        log_debug("📚 NO MCP TOOLS: Using internal tools only")
                        
                except concurrent.futures.TimeoutError:
                    print("⏰ MCP TIMEOUT: MCP servers not responding - using internal tools only")
                    mcp_tool_map = {}
                
        except Exception as e:
            print(f"❌ MCP ERROR: {e} - Using internal tools only")
            mcp_tool_map = {}
    else:
        log_debug("📚 NO MCP TOOLS REQUESTED: Skipping MCP initialization")
        mcp_tool_map = {}
    
    # Map LaunchDarkly tool names to actual MCP tool names
    ld_to_mcp_mapping = {
        "arxiv_search": "search_papers", 
        "semantic_scholar": "search_semantic_scholar"
    }
    
    log_debug(f"🔧 PROCESSING TOOLS: {tools_list}")
    log_debug(f"🗺️  MCP TOOL MAP KEYS: {list(mcp_tool_map.keys())}")
    
    for tool_name in tools_list:
        log_debug(f"⚙️  Processing tool: {tool_name}")
        
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
            log_debug(f"📚 INTERNAL TOOL ADDED: Basic vector search (search_v1)")
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
            log_debug(f"📚 INTERNAL TOOL ADDED: Advanced vector search with embeddings (search_v2)")
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
            log_debug(f"📊 INTERNAL TOOL ADDED: BM25 reranking algorithm (reranking)")
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
                    
                    async def _arun(self, config=None, **kwargs) -> str:
                        """Execute the wrapped MCP tool asynchronously."""
                        try:
                            # Handle nested kwargs structure from MCP tools
                            if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
                                actual_kwargs = kwargs['kwargs']
                            else:
                                actual_kwargs = kwargs
                            
                            # Use await to call the async tool method
                            if hasattr(self.wrapped_tool, '_arun'):
                                result = await self.wrapped_tool._arun(config=config, **actual_kwargs)
                            elif hasattr(self.wrapped_tool, 'ainvoke'):
                                invoke_args = dict(actual_kwargs)
                                invoke_args['config'] = config
                                result = await self.wrapped_tool.ainvoke(invoke_args)
                            elif hasattr(self.wrapped_tool, 'invoke'):
                                # Some tools might be sync, run in executor
                                invoke_args = dict(actual_kwargs)
                                invoke_args['config'] = config
                                loop = asyncio.get_event_loop()
                                result = await loop.run_in_executor(None, self.wrapped_tool.invoke, invoke_args)
                            else:
                                # Fallback, attempt to run in default executor
                                loop = asyncio.get_event_loop()
                                result = await loop.run_in_executor(None, self.wrapped_tool, config, **actual_kwargs)

                            # Format result
                            if isinstance(result, dict):
                                return json.dumps(result, indent=2)
                            elif isinstance(result, list):
                                return json.dumps(result, indent=2)
                            else:
                                return str(result)
                        except Exception as e:
                            print(f"❌ MCP TOOL ERROR: {e}")
                            return f"MCP tool error: {str(e)}"
                    
                    def _run(self, config=None, **kwargs) -> str:
                        """Synchronous fallback - run async version in new event loop."""
                        try:
                            # Create new event loop for sync execution
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(self._arun(config=config, **kwargs))
                                return result
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"❌ MCP TOOL SYNC ERROR: {e}")
                            return f"MCP tool error: {str(e)}"
                
                wrapped_mcp_tool = MCPToolWrapper(mcp_tool, tool_name)
                available_tools.append(wrapped_mcp_tool)
                print(f"🔬 MCP TOOL ADDED (WRAPPED): {tool_name} -> {mcp_tool_name} via MCP server")
            else:
                print(f"❌ MCP TOOL UNAVAILABLE: {tool_name} requested but not in map {list(mcp_tool_map.keys())} - SKIPPING")
        else:
            print(f"❓ UNKNOWN TOOL REQUESTED: {tool_name} - SKIPPING")
    
    # Initialize model based on LaunchDarkly config using LDAI SDK pattern
    model_name_attr = config.model.name if hasattr(config.model, 'name') else 'claude-3-haiku-20240307'
    
    # Get provider name from config
    provider_name = None
    if config.provider and hasattr(config.provider, 'name'):
        provider_name = config.provider.name
    
    model = get_model_instance(model_name_attr, 0.0, provider_name)
    
    # Debug: Show final available tools
    log_debug(f"🔧 FINAL AVAILABLE TOOLS: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in available_tools]}")
    
    # Store config values for nested functions
    config_instructions = config.instructions
    
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
                
                # Apply LaunchDarkly tool configuration parameters
                if tool_name in tool_configs:
                    ld_params = tool_configs[tool_name]
                    log_verbose(f"🔧 APPLYING LD CONFIG: {tool_name} config = {ld_params}")
                    
                    # Extract parameters from JSON schema structure
                    if 'properties' in ld_params:
                        properties = ld_params['properties']
                        for param_name, param_config in properties.items():
                            # Apply LaunchDarkly defaults if not provided in tool call
                            if param_name not in tool_args and 'default' in param_config:
                                tool_args[param_name] = param_config['default']
                                print(f"🔧 APPLIED LD DEFAULT: {param_name} = {param_config['default']}")
                    else:
                        print(f"⚠️ LD CONFIG: No 'properties' found in schema for {tool_name}")
                
                log_verbose(f"🔧 EXECUTING TOOL: {tool_name} with args: {tool_args}")
                
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
                                    # More flexible matching - check if this is a search_v2 tool result
                                    if ('search_v2' in str(msg.tool_call_id).lower() or 
                                        (hasattr(msg, 'content') and 'Found' in str(msg.content) and 'relevant document' in str(msg.content))):
                                        latest_search_message = msg
                                        break
                            
                            if latest_search_message:
                                # Pass the raw search_v2 output content to reranking tool
                                tool_args['results'] = latest_search_message.content
                                print(f"🔧 RERANKING: Found search_v2 output in message history, passing to tool")
                            else:
                                # Fallback: no search_v2 results found
                                tool_args['results'] = ""
                                print(f"⚠️ RERANKING: No search_v2 output found in message history")
                        
                        # For MCP tools, ensure config parameter is handled
                        if tool_name in ['arxiv_search', 'semantic_scholar']:
                            # MCP tools expect config parameter
                            if 'config' not in tool_args:
                                tool_args['config'] = None
                        
                        # Execute the tool
                        result = tool_to_execute._run(**tool_args)
                        
                        # Analyze search_v2 results for relevance threshold
                        if tool_name == "search_v2":
                            try:
                                import re
                                # Extract relevance scores from search_v2 result
                                relevance_pattern = r'\[Relevance: ([\d.]+)\]'
                                scores = re.findall(relevance_pattern, str(result))
                                if scores:
                                    max_score = max(float(score) for score in scores)
                                    print(f"🔍 SEARCH_V2 MAX RELEVANCE: {max_score}")
                                    
                                    # If relevance is low, suggest escalation
                                    if max_score < 0.6:
                                        print(f"⚠️ LOW RELEVANCE DETECTED ({max_score}) - Consider external research tools")
                                        # Store low relevance flag in state for potential escalation
                                        state["low_relevance_detected"] = True
                                        state["last_search_query"] = tool_args.get('query', '')
                                else:
                                    print(f"🔍 SEARCH_V2: No relevance scores found in result")
                            except Exception as e:
                                print(f"⚠️ Error analyzing search_v2 relevance: {e}")
                        
                        # Search results are automatically stored in ToolMessage content
                        # No need for manual state management
                        
                    except Exception as e:
                        result = f"Error executing {tool_name}: {str(e)}"
                        print(f"❌ TOOL ERROR: {result}")
                
                # Create tool message
                tool_message = ToolMessage(content=str(result), tool_call_id=tool_id)
                tool_results.append(tool_message)
                
                log_verbose(f"🔧 TOOL RESULT: {tool_name} -> {str(result)[:200]}...")
            
            return {"messages": tool_results}
        
        tool_node = custom_tool_node
    else:
        print(f"⚠️  NO TOOLS AVAILABLE: Agent will work in model-only mode")
        # Create empty tool node that won't be used
        def empty_tool_node(state: AgentState):
            """Empty tool node for when no tools are available"""
            return {"messages": []}
        tool_node = empty_tool_node
    
    def should_continue(state: AgentState):
        """Decide whether to continue with tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Count tool calls and track search queries from all messages in the conversation
        total_tool_calls = 0
        recent_tool_calls = []
        recent_search_queries = []
        
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                total_tool_calls += len(message.tool_calls)
                for tool_call in message.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call.get('args', {})
                    recent_tool_calls.append(tool_name)
                    
                    # Extract search query from tool arguments
                    search_query = tool_args.get('query', '') or tool_args.get('search_query', '') or tool_args.get('q', '')
                    if search_query and tool_name in ['search_v1', 'search_v2', 'search_papers', 'search_semantic_scholar']:
                        recent_search_queries.append(search_query.lower().strip())
                    
                    query_display = f"query: '{search_query}'" if search_query else "no query found"
                    
                    # Log tool usage type with search terms
                    if tool_name in ['search_papers', 'search_semantic_scholar']:
                        log_student(f"🔧 EXECUTING: {tool_name} → external research")
                        log_debug(f"🔬 MCP TOOL CALLED: {tool_name} ({query_display}) (external research server)")
                    elif tool_name in ['search_v1', 'search_v2', 'reranking']:
                        # Create educational tool execution log
                        if tool_name == "search_v2":
                            # Note: result is not available in this scope, so we can't extract relevance here
                            log_student(f"🔧 EXECUTING: {tool_name} → {query_display.split(':')[1].strip() if ':' in query_display else query_display}")
                        elif tool_name == "reranking":
                            log_student(f"🔧 EXECUTING: {tool_name} → BM25 reordered results")
                        else:
                            log_student(f"🔧 EXECUTING: {tool_name} → {query_display}")
                        
                        log_debug(f"📚 INTERNAL TOOL CALLED: {tool_name} ({query_display}) (local processing)")
                    else:
                        print(f"🔧 UNKNOWN TOOL CALLED: {tool_name} ({query_display})")
        
        # Check for repeated identical search queries - stop if same query used 3+ times
        if len(recent_search_queries) >= 3:
            for query in set(recent_search_queries):
                query_count = recent_search_queries.count(query)
                if query_count >= 3:
                    print(f"🛑 STOPPING REPEATED SEARCH: Query '{query}' used {query_count} times - no useful results found")
                    # Add instruction to try different terms or stop searching
                    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        # Agent is about to make another tool call - inject guidance
                        state["messages"].append(HumanMessage(content=f"""
You've searched for "{query}" multiple times without finding useful results. Either:
1. Try completely different search terms that are more specific or use synonyms
2. If no relevant information exists in the knowledge base, simply respond that the information is not available
Do not repeat the same search query again."""))
                    return "end"
        
        # RELAXED: Allow up to 4 consecutive calls of the same tool before stopping
        if len(recent_tool_calls) >= 4:
            last_4_tools = recent_tool_calls[-4:]
            if len(set(last_4_tools)) == 1:  # Same tool used 4 times in a row
                print(f"🛑 STOPPING TOOL LOOP: '{last_4_tools[-1]}' used 4+ times consecutively - ending workflow")
                return "end"
        
        # Stop if any single tool is used more than 5 times total in conversation
        for tool_name in set(recent_tool_calls):
            if recent_tool_calls.count(tool_name) >= 5:
                print(f"🛑 STOPPING TOOL LOOP: '{tool_name}' used {recent_tool_calls.count(tool_name)} times total - ending workflow")
                return "end"
        
        # Use max_tool_calls extracted from config
        # print(f"DEBUG: should_continue - total_tool_calls: {total_tool_calls}, max: {max_tool_calls}")
        # print(f"DEBUG: Recent tool calls: {recent_tool_calls[-5:]}")  # Show last 5
        
        # If we've hit the max tool calls limit, end
        if total_tool_calls >= max_tool_calls:
            # print(f"DEBUG: Hit max tool calls limit ({max_tool_calls}), ending")
            return "end"
        
        # If no tools are available, never route to tools
        if not available_tools:
            # print("DEBUG: No tools available, ending")
            return "end"
        
        # If the last message has tool calls, continue to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # print(f"DEBUG: Last message has {len(last_message.tool_calls)} tool calls, continuing to tools")
            return "tools"
        
        # Otherwise, we're done
        # print("DEBUG: No more tool calls needed, ending")
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
            
            # print(f"DEBUG: call_model - total_tool_calls: {total_tool_calls}, messages: {len(messages)}")
            
            # Add system message with instructions if this is the first call
            if len(messages) == 1:  # Only user message
                # Use max_tool_calls extracted from config
                
                if available_tools:
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
                    
                    IMPORTANT: When you receive search results from these tools, prioritize that information over your general knowledge. Base your responses on the search results whenever possible.
                    """
                else:
                    # No tools available - explain limitations gracefully
                    system_prompt = f"""
                    {config_instructions}
                    
                    IMPORTANT: You currently have no access to search tools or external documents. 
                    You can only work with your built-in knowledge. Please inform users that:
                    - You cannot search the knowledge base or internal documents
                    - You cannot access external research databases
                    - You can only provide general information based on your training data
                    
                    Be helpful within these limitations and suggest users contact support if they need specific document searches.
                    """
                
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Simple and effective: Check for tool overuse and REMOVE tools if needed
            recent_tool_calls = []
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        recent_tool_calls.append(tool_call['name'])
            
            # If at max tool calls, disable tools for final completion
            if total_tool_calls >= max_tool_calls:
                print(f"🛑 DISABLING TOOLS: Reached maximum tool calls ({total_tool_calls}/{max_tool_calls})")
                
                # Add synthesis instruction for final completion
                synthesis_prompt = HumanMessage(content="""
                You've now gathered information from multiple sources. Please synthesize your findings into a comprehensive answer that:
                1. Summarizes the key insights from your research
                2. Compares information from different sources (internal knowledge, ArXiv, Semantic Scholar)
                3. Provides actionable conclusions and recommendations
                4. Addresses the user's original question directly
                """)
                messages.append(synthesis_prompt)
                
                # Use the base model without any tools bound for final completion  
                model_name_for_completion = config.model.name if hasattr(config.model, 'name') else 'claude-3-haiku-20240307'
                completion_provider = None
                if config.provider and hasattr(config.provider, 'name'):
                    completion_provider = config.provider.name
                completion_model = get_model_instance(model_name_for_completion, 0.0, completion_provider)
                response = completion_model.invoke(messages)
                print(f"🎯 FORCED SYNTHESIS: Model completing with synthesis instructions")
                return {"messages": [response]}
            
            # Track the core model invocation with LaunchDarkly tracker when available
            tracker = getattr(config, 'tracker', None)
            # print(f"🔍 SUPPORT AGENT DEBUG: config_manager={config_manager is not None}, tracker={tracker is not None}")
            if tracker:
                log_verbose(f"🔍 TRACKER TYPE: {type(tracker)}")
                log_verbose(f"🔍 TRACKER METHODS: {[m for m in dir(tracker) if not m.startswith('_')]}")
            
            if config_manager and tracker:
                log_debug(f"🚀 USING LAUNCHDARKLY TRACKER for model call")
                response = config_manager.track_metrics(
                    config.tracker,
                    lambda: model.invoke(messages)
                )
            else:
                print(f"⚠️  NO TRACKER AVAILABLE - using direct model call")
                response = model.invoke(messages)
            # print(f"DEBUG: Model response received, has_tool_calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")
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
        
        print(f"🔧 SUPPORT AGENT RETURNING: 📊 tool_calls: {tool_calls}")
        log_debug(f"   📊 tool_details: {tool_details}")
        
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
    
    log_debug("✅ SUPPORT AGENT COMPILED: Ready for execution")
    return workflow.compile()