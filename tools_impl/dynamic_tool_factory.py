"""
Dynamic Tool Factory for LaunchDarkly AI Configuration
Recreates the dynamic tool loading that was lost in the architecture change
"""
from typing import Dict, List, Any, Optional
import os
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
        description: str = "Semantic search through the knowledge base. Use for technical questions and concepts."
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
        description: str = "Rerank search results by relevance. Use after search to improve result ordering."
        args_schema: type[BaseModel] = DynamicRerankingInput

        def _run(self, query: str, results: List[Dict[str, Any]] = None, **kwargs) -> str:
            # Import and delegate to actual implementation
            from tools_impl.reranking import RerankingTool
            actual_tool = RerankingTool()
            return actual_tool._run(query, results, **kwargs)

    return DynamicRerankingTool()


def create_dynamic_tools_from_launchdarkly(config) -> List[BaseTool]:
    """
    Main function to create all tools dynamically from LaunchDarkly configuration.
    This replaces the hardcoded tool instantiation.
    """
    tools_list, tool_configs = extract_tool_configs_from_launchdarkly(config)

    available_tools = []

    for tool_name in tools_list:
        tool_config = tool_configs.get(tool_name, {})
        tool_instance = create_dynamic_tool_instance(tool_name, tool_config)

        if tool_instance:
            available_tools.append(tool_instance)
            log_debug(f"DYNAMIC TOOL CREATED: {tool_name}")
        else:
            log_debug(f"DYNAMIC TOOL FAILED: {tool_name}")

    log_student(f"DYNAMIC TOOLS LOADED: {[tool.name for tool in available_tools]}")

    return available_tools