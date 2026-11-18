"""
Dynamic Tool Factory for LaunchDarkly AI Configuration

Builds the support agent's tools from the tool definitions in its AI Config.
"""
from typing import Dict, List, Any, Optional
import os
import asyncio
import concurrent.futures
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
from utils.logger import log_student, log_debug


def extract_tool_configs_from_launchdarkly(config) -> tuple[List[str], Dict[str, Any]]:
    """
    Extract tool configurations from LaunchDarkly AI Config.
    Returns: (tools_list, tool_configs)
    """
    tool_configs = {tool['name']: tool.get('parameters', {}) for tool in config.parameters.get('tools', [])}
    tools_list = list(tool_configs)

    log_debug(f"EXTRACTED TOOLS FROM LAUNCHDARKLY: {tools_list}")
    if tool_configs:
        log_debug(f" TOOL CONFIGS FROM LAUNCHDARKLY: {tool_configs}")

    return tools_list, tool_configs


def create_dynamic_tool_instance(tool_name: str, tool_config: Dict[str, Any]) -> Optional[BaseTool]:
    """
    Create a tool instance dynamically configured from LaunchDarkly.

    This replaces hardcoded tool schemas with LaunchDarkly-provided configurations.
    """
    log_debug(f"Creating dynamic tool: {tool_name}")

    if tool_name == "search_v1":
        from tools_impl.search_v1 import SearchToolV1
        return SearchToolV1()
    elif tool_name == "search_v2":
        return _create_dynamic_search_v2(tool_config)
    elif tool_name == "reranking":
        return _create_dynamic_reranking_tool(tool_config)
    elif tool_name in ["arxiv_search", "openalex_search"]:
        return _create_dynamic_mcp_tool(tool_name)
    else:
        log_debug(f"❓ UNKNOWN TOOL: {tool_name}")
        return None


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

            # Create Pydantic field
            if field_name in tool_config.get('required', []):
                field_definitions[field_name] = (field_type, Field(description=field_description))
            else:
                field_definitions[field_name] = (field_type, Field(default=field_default, description=field_description))

        # Create dynamic Pydantic model
        DynamicSearchV2Input = create_model('DynamicSearchV2Input', **field_definitions)

    else:
        # Fallback to minimal schema
        log_debug("SEARCH_V2: No LaunchDarkly config found, using minimal schema")
        class DynamicSearchV2Input(BaseModel):
            query: str
            top_k: Optional[int] = 3

    # Create dynamic tool class
    class DynamicSearchToolV2(BaseTool):
        name: str = "search_v2"
        description: str = "Semantic search using vector embeddings"
        args_schema: type[BaseModel] = DynamicSearchV2Input

        def _run(self, query: str, top_k: int = 3) -> str:
            from tools_impl.search_v2 import SearchToolV2
            return SearchToolV2()._run(query, top_k)

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
            # Map LaunchDarkly types to Python types; the results array holds search_v2 items
            field_type = List[Dict[str, Any]] if field_config.get('type') == 'array' else str
            field_definitions[field_name] = (field_type, Field(description=field_config.get('description', '')))

        # Create dynamic Pydantic model
        DynamicRerankingInput = create_model('DynamicRerankingInput', **field_definitions)

    else:
        # Fallback to minimal schema matching LaunchDarkly
        log_debug("RERANKING: No LaunchDarkly config found, using minimal schema")
        class DynamicRerankingInput(BaseModel):
            query: str
            results: Optional[List[Dict[str, Any]]] = None

    # Create dynamic tool class
    class DynamicRerankingTool(BaseTool):
        name: str = "reranking"
        description: str = "Reorders results by relevance using BM25 algorithm"
        args_schema: type[BaseModel] = DynamicRerankingInput

        def _run(self, query: str, results: List[Dict[str, Any]] = None, **kwargs) -> str:
            from tools_impl.reranking import RerankingTool
            return RerankingTool()._run(query, results, **kwargs)

    return DynamicRerankingTool()


def _create_mcp_tool_wrapper(mcp_tool, ld_name: str):
    """Create wrapper for MCP tool that properly handles async/sync execution"""

    class MCPToolWrapper(BaseTool):
        name: str = ld_name  # Use LaunchDarkly name
        description: str = mcp_tool.description
        wrapped_tool: Any = None  # Declare as Pydantic field
        args_schema: Any = None  # Will be set to wrapped tool's schema

        def __init__(self, mcp_tool, ld_name):
            super().__init__()
            object.__setattr__(self, 'wrapped_tool', mcp_tool)
            object.__setattr__(self, 'name', ld_name)
            object.__setattr__(self, 'args_schema', mcp_tool.args_schema)

        async def _arun(self, config=None, **kwargs) -> str:
            """Execute the wrapped MCP tool asynchronously."""
            try:
                # Handle nested kwargs structure from MCP tools
                if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
                    kwargs = kwargs['kwargs']

                print(f"🔍 MCP TOOL {self.name} received args: {kwargs}")
                result = await self.wrapped_tool._arun(config=config, **kwargs)
                return str(result)

            except Exception as e:
                import traceback
                log_debug(f"MCP TOOL TRACEBACK: {traceback.format_exc()}")
                print(f"⚠️ MCP TOOL ERROR ({self.name}): {e}")
                return f"MCP tool error: {str(e)}"

        def _run(self, **kwargs) -> str:
            """Execute the wrapped MCP tool synchronously (MCP tools are async-only)."""
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(self._arun(**kwargs))
            # Already inside an event loop, so run in a fresh loop on another thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, self._arun(**kwargs)).result(timeout=30)

    return MCPToolWrapper(mcp_tool, ld_name)


def _create_dynamic_mcp_tool(tool_name: str) -> Optional[BaseTool]:
    """Create an MCP tool, loading the MCP servers on first use"""
    # Disable MCP tools in CI safe mode to reduce flakiness while preserving core functionality
    if os.getenv("CI_SAFE_MODE", "").lower() in {"1", "true", "yes"}:
        log_debug(f"CI_SAFE_MODE enabled: skipping MCP tool {tool_name}")
        return None

    from tools_impl.mcp_research_tools import MCPResearchTools

    def initialize_mcp_tools():
        """Initialize MCP tools in a separate thread with new event loop"""
        mcp_client = MCPResearchTools()
        try:
            asyncio.run(mcp_client.initialize())
        except Exception as e:
            log_debug(f"MCP initialization error: {e}")
        return mcp_client.tools

    # Run MCP initialization in thread with timeout
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        try:
            mcp_tool = executor.submit(initialize_mcp_tools).result(timeout=30).get(tool_name)
        except concurrent.futures.TimeoutError:
            log_debug(f"MCP TIMEOUT: {tool_name} not available")
            return None

    if mcp_tool is None:
        return None
    log_debug(f"MCP TOOL CREATED: {tool_name} -> {mcp_tool.name}")
    return _create_mcp_tool_wrapper(mcp_tool, tool_name)


def create_dynamic_tools_from_launchdarkly(config) -> List[BaseTool]:
    """
    Main function to create all tools dynamically from LaunchDarkly configuration.
    This replaces the hardcoded tool instantiation.
    """
    tools_list, tool_configs = extract_tool_configs_from_launchdarkly(config)

    available_tools = []

    for tool_name in tools_list:
        tool_instance = create_dynamic_tool_instance(tool_name, tool_configs[tool_name])

        if tool_instance:
            available_tools.append(tool_instance)
            log_debug(f"DYNAMIC TOOL CREATED: {tool_name}")
        else:
            log_debug(f"DYNAMIC TOOL FAILED: {tool_name}")

    log_student(f"DYNAMIC TOOLS LOADED: {[tool.name for tool in available_tools]}")

    return available_tools
