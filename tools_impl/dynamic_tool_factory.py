"""
Dynamic Tool Factory for LaunchDarkly AI Configuration
Recreates the dynamic tool loading that was lost in the architecture change
"""
from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
from utils.logger import log_student, log_debug, log_verbose
import json


def extract_tool_configs_from_launchdarkly(config) -> tuple[List[str], Dict[str, Any]]:
    """
    Extract tool configurations from LaunchDarkly AI Config.
    Returns: (tools_list, tool_configs)

    This restores the functionality that was lost when switching from StateGraph to create_react_agent.
    """
    tools_list = []
    tool_configs = {}

    # Get tools from the initial config (tools are stable, instructions are dynamic)
    if hasattr(config, 'tools') and config.tools:
        tools_list = list(config.tools)

    # Try to get tool configurations from config dict structure
    try:
        config_dict = config.to_dict()
        if 'model' in config_dict and 'parameters' in config_dict['model'] and 'tools' in config_dict['model']['parameters']:
            tools_data = config_dict['model']['parameters']['tools']
            for tool in tools_data:
                if 'name' in tool:
                    tool_name = tool['name']
                    if tool_name not in tools_list:
                        tools_list.append(tool_name)
                    # Extract tool parameters/schema from LaunchDarkly
                    tool_configs[tool_name] = tool.get('parameters', {})

        log_debug(f"EXTRACTED TOOLS FROM LAUNCHDARKLY: {tools_list}")
        if tool_configs:
            log_verbose(f" TOOL CONFIGS FROM LAUNCHDARKLY: {tool_configs}")

    except Exception as e:
        log_debug(f"Error extracting tool configs from LaunchDarkly: {e}")
        pass  # Fallback to just the tools list and defaults

    return tools_list, tool_configs


def create_dynamic_tool_instance(tool_name: str, tool_config: Dict[str, Any]) -> Optional[BaseTool]:
    """
    Create a tool instance dynamically configured from LaunchDarkly.

    This replaces hardcoded tool schemas with LaunchDarkly-provided configurations.
    """
    log_debug(f"Creating dynamic tool: {tool_name}")

    if tool_name == "search_v1":
        return _create_dynamic_search_v1(tool_config)
    elif tool_name == "search_v2":
        return _create_dynamic_search_v2(tool_config)
    elif tool_name == "reranking":
        return _create_dynamic_reranking_tool(tool_config)
    elif tool_name in ["arxiv_search", "semantic_scholar"]:
        return _create_dynamic_mcp_tool(tool_name, tool_config)
    else:
        log_debug(f"❓ UNKNOWN TOOL: {tool_name}")
        return None


def _create_dynamic_search_v1(tool_config: Dict[str, Any]) -> BaseTool:
    """Create search_v1 tool with LaunchDarkly configuration"""
    from tools_impl.search_v1 import SearchToolV1

    # Create base tool instance
    tool = SearchToolV1()

    # Apply LaunchDarkly configuration if available
    if tool_config and 'properties' in tool_config:
        log_debug(f"SEARCH_V1: Applying LaunchDarkly config")
        # Could override defaults here based on LaunchDarkly config
        # For now, just log that config is available
        pass

    return tool


def _create_dynamic_search_v2(tool_config: Dict[str, Any]) -> BaseTool:
    """Create search_v2 tool with LaunchDarkly configuration"""

    # Create dynamic input schema based on LaunchDarkly tool definition
    if tool_config and 'properties' in tool_config:
        properties = tool_config['properties']
        log_debug(f"SEARCH_V2: Creating dynamic schema from LaunchDarkly: {properties}")

        # Build Pydantic field definitions from LaunchDarkly schema
        field_definitions = {}

        for field_name, field_config in properties.items():
            field_type = str  # Default to string
            field_default = None
            field_description = field_config.get('description', '')

            # Map LaunchDarkly JSON schema types to Python types
            if field_config.get('type') == 'number':
                field_type = int
                field_default = 3  # Default for top_k
            elif field_config.get('type') == 'string':
                field_type = str

            # Create Pydantic field
            if field_name in tool_config.get('required', []):
                field_definitions[field_name] = (field_type, Field(description=field_description))
            else:
                field_definitions[field_name] = (field_type, Field(default=field_default, description=field_description))

        # Create dynamic Pydantic model
        DynamicSearchV2Input = create_model('DynamicSearchV2Input', **field_definitions)

    else:
        # Fallback to minimal schema
        log_debug(f"SEARCH_V2: No LaunchDarkly config found, using minimal schema")
        class DynamicSearchV2Input(BaseModel):
            query: str
            top_k: Optional[int] = 3

    # Create dynamic tool class
    class DynamicSearchToolV2(BaseTool):
        name: str = "search_v2"
        description: str = "Semantic search using vector embeddings"
        args_schema: type[BaseModel] = DynamicSearchV2Input

        def _run(self, query: str, top_k: int = 3) -> str:
            # Import and delegate to actual implementation
            from tools_impl.search_v2 import SearchToolV2
            actual_tool = SearchToolV2()
            return actual_tool._run(query, top_k)

    return DynamicSearchToolV2()


def _create_dynamic_reranking_tool(tool_config: Dict[str, Any]) -> BaseTool:
    """Create reranking tool with LaunchDarkly configuration"""

    # Create dynamic input schema based on LaunchDarkly tool definition
    if tool_config and 'properties' in tool_config:
        properties = tool_config['properties']
        log_debug(f"RERANKING: Creating dynamic schema from LaunchDarkly: {properties}")

        # Build Pydantic field definitions from LaunchDarkly schema
        field_definitions = {}

        for field_name, field_config in properties.items():
            field_description = field_config.get('description', '')

            # Map LaunchDarkly types to Python types
            if field_config.get('type') == 'array':
                field_type = List[Dict[str, Any]]  # For results array
            elif field_config.get('type') == 'string':
                field_type = str
            else:
                field_type = str  # Default

            # Create Pydantic field
            field_definitions[field_name] = (field_type, Field(description=field_description))

        # Create dynamic Pydantic model
        DynamicRerankingInput = create_model('DynamicRerankingInput', **field_definitions)

    else:
        # Fallback to minimal schema matching LaunchDarkly
        log_debug(f"RERANKING: No LaunchDarkly config found, using minimal schema")
        class DynamicRerankingInput(BaseModel):
            query: str
            results: Optional[List[Dict[str, Any]]] = None

    # Create dynamic tool class
    class DynamicRerankingTool(BaseTool):
        name: str = "reranking"
        description: str = "Reorders results by relevance using BM25 algorithm"
        args_schema: type[BaseModel] = DynamicRerankingInput

        def _run(self, query: str, results: List[Dict[str, Any]] = None, **kwargs) -> str:
            # Import and delegate to actual implementation
            from tools_impl.reranking import RerankingTool
            actual_tool = RerankingTool()
            return actual_tool._run(query, results, **kwargs)

    return DynamicRerankingTool()


def _create_dynamic_mcp_tool(tool_name: str, tool_config: Dict[str, Any]) -> Optional[BaseTool]:
    """Create MCP tool with LaunchDarkly configuration using working wrapper pattern"""
    try:
        from tools_impl.mcp_research_tools import get_research_tools
        import asyncio
        import concurrent.futures

        def initialize_mcp_tools():
            """Initialize MCP tools in a separate thread with new event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                from tools_impl.mcp_research_tools import MCPResearchTools
                mcp_client = MCPResearchTools()
                result = loop.run_until_complete(mcp_client.initialize())

                available_mcp_tools = []
                if hasattr(mcp_client, 'tools') and mcp_client.tools:
                    for tool_name_key, tool_instance in mcp_client.tools.items():
                        available_mcp_tools.append(tool_instance)

                return available_mcp_tools

            except Exception as e:
                log_debug(f"MCP initialization error: {e}")
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

                # Map LaunchDarkly tool names to actual MCP tool names
                ld_to_mcp_mapping = {
                    "arxiv_search": "search_papers",
                    "semantic_scholar": "search_semantic_scholar"
                }

                mcp_tool_name = ld_to_mcp_mapping.get(tool_name)
                if mcp_tool_name:
                    # Find matching MCP tool
                    for mcp_tool in mcp_tools:
                        if hasattr(mcp_tool, 'name') and mcp_tool_name in mcp_tool.name.lower():
                            # Create wrapper like in working version
                            wrapped_tool = _create_mcp_tool_wrapper(mcp_tool, tool_name)
                            log_debug(f"MCP TOOL CREATED: {tool_name} -> {mcp_tool_name}")
                            return wrapped_tool

            except concurrent.futures.TimeoutError:
                log_debug(f"MCP TIMEOUT: {tool_name} not available")

    except ImportError:
        log_debug(f"MCP IMPORT ERROR: {tool_name} not available")

    return None


def _create_mcp_tool_wrapper(mcp_tool, ld_name: str):
    """Create wrapper for MCP tool using the working pattern from old version"""
    from langchain.tools import BaseTool
    from typing import Any
    import json

    class MCPToolWrapper(BaseTool):
        name: str = ld_name  # Use LaunchDarkly name
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
                    import asyncio
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = await asyncio.get_event_loop().run_in_executor(
                            executor, lambda: self.wrapped_tool.invoke(actual_kwargs)
                        )
                else:
                    raise ValueError(f"MCP tool {self.name} has no callable method")

                return str(result)

            except Exception as e:
                log_debug(f"MCP TOOL ASYNC ERROR: {e}")
                return f"MCP tool error: {str(e)}"

        def _run(self, **kwargs) -> str:
            """Execute the wrapped MCP tool synchronously."""
            try:
                # Handle nested kwargs structure
                if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
                    actual_kwargs = kwargs['kwargs']
                else:
                    actual_kwargs = kwargs

                # MCP tools are async-only, so always use async execution
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create new loop for sync execution in thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._arun(**actual_kwargs))
                            result = future.result(timeout=30)
                    else:
                        result = loop.run_until_complete(self._arun(**actual_kwargs))
                except RuntimeError:
                    # No event loop, create one
                    result = asyncio.run(self._arun(**actual_kwargs))

                return str(result)

            except Exception as e:
                log_debug(f"MCP TOOL SYNC ERROR: {e}")
                return f"MCP tool error: {str(e)}"

    return MCPToolWrapper(mcp_tool, ld_name)


def _create_research_fallback_tool(tool_name: str) -> Optional[BaseTool]:
    """Create fallback research tool when MCP isn't available"""
    from langchain.tools import BaseTool
    from pydantic import BaseModel, Field

    class ResearchInput(BaseModel):
        """Input schema for research tools"""
        query: str = Field(description="Research query for academic papers")
        max_results: int = Field(default=5, description="Maximum number of results to return")

    class ResearchFallbackTool(BaseTool):
        name: str = tool_name
        description: str = ""
        args_schema: type = ResearchInput

        def __init__(self, tool_name: str):
            super().__init__()
            if tool_name == "arxiv_search":
                object.__setattr__(self, 'description', "Search ArXiv for academic papers (fallback: uses enhanced vector search)")
            elif tool_name == "semantic_scholar":
                object.__setattr__(self, 'description', "Search Semantic Scholar for academic papers (fallback: uses enhanced vector search)")
            object.__setattr__(self, 'name', tool_name)

        def _run(self, query: str, max_results: int = 5) -> str:
            """Fallback research using enhanced vector search"""
            try:
                # Use the existing vector search tools as fallback
                from tools_impl.search_v2 import SearchToolV2
                from tools_impl.reranking import RerankingTool

                # Enhanced search with reranking for better research results
                search_tool = SearchToolV2()
                rerank_tool = RerankingTool()

                # Get initial results
                search_results = search_tool.run(f"academic research papers {query}")

                # Rerank for relevance
                if search_results and "No relevant" not in search_results:
                    reranked_results = rerank_tool.run(f"query:{query}\nresults:{search_results}")

                    # Format as research paper results
                    result = f"RESEARCH RESULTS for '{query}' (via enhanced vector search):\n\n"
                    result += f"Note: Using fallback search due to MCP unavailability. Results are from internal documentation.\n\n"
                    result += reranked_results

                    return result
                else:
                    return f"No research papers found for query: {query}. Try different search terms."

            except Exception as e:
                return f"Research search error: {str(e)}"

    return ResearchFallbackTool(tool_name)


def create_dynamic_tools_from_launchdarkly(config) -> List[BaseTool]:
    """
    Main function to create all tools dynamically from LaunchDarkly configuration.
    This replaces the hardcoded tool instantiation.
    """
    tools_list, tool_configs = extract_tool_configs_from_launchdarkly(config)

    # Debug: Show what tools LaunchDarkly is configured with
    log_debug(f"TOOLS FROM LAUNCHDARKLY CONFIG: {tools_list}")

    available_tools = []

    for tool_name in tools_list:
        tool_config = tool_configs.get(tool_name, {})
        tool_instance = create_dynamic_tool_instance(tool_name, tool_config)

        if tool_instance:
            available_tools.append(tool_instance)
            log_debug(f"DYNAMIC TOOL CREATED: {tool_name}")
        else:
            # Create fallback tools for MCP research when MCP isn't available
            if tool_name in ["arxiv_search", "semantic_scholar"]:
                fallback_tool = _create_research_fallback_tool(tool_name)
                if fallback_tool:
                    available_tools.append(fallback_tool)
                    log_debug(f"MCP FALLBACK TOOL CREATED: {tool_name}")
                else:
                    log_debug(f"MCP TOOL NOT AVAILABLE: {tool_name}")
            else:
                log_debug(f"DYNAMIC TOOL FAILED: {tool_name}")

    # Show final loaded tools (suppress MCP tool absence for variations that don't include them)
    loaded_tool_names = [tool.name for tool in available_tools]
    mcp_tools_in_config = any(name in tools_list for name in ["arxiv_search", "semantic_scholar"])
    mcp_tools_loaded = any(name in loaded_tool_names for name in ["arxiv_search", "semantic_scholar"])

    if mcp_tools_in_config and not mcp_tools_loaded:
        log_student(f"TOOLS LOADED: {loaded_tool_names} (MCP tools unavailable)")
    else:
        log_student(f"TOOLS LOADED: {loaded_tool_names}")

    return available_tools