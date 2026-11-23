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

    # Configs are plain dicts now, so there is no to_dict() and no attribute
    # access. Both lookups below used to fail into the except branch, which
    # returned no tools at all rather than erroring.
    config = config or {}

    # LaunchDarkly 1.1.0 serves top-level `tools` as a dict keyed by tool name,
    # where each entry carries `name`, `description`, and `parameters`. Local
    # fixtures may also pass `tools` as a list of names or tool dicts.
    raw_tools = config.get('tools')
    if isinstance(raw_tools, dict):
        for key, spec in raw_tools.items():
            spec_dict = spec if isinstance(spec, dict) else {}
            tool_name = spec_dict.get('name') or key
            if tool_name not in tools_list:
                tools_list.append(tool_name)
            params = dict(spec_dict.get('parameters') or {})
            if spec_dict.get('description'):
                params['description'] = spec_dict['description']
            tool_configs[tool_name] = params
    elif isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, dict) and item.get('name'):
                tool_name = item['name']
                if tool_name not in tools_list:
                    tools_list.append(tool_name)
                params = dict(item.get('parameters') or {})
                if item.get('description'):
                    params['description'] = item['description']
                tool_configs[tool_name] = params
            elif isinstance(item, str) and item not in tools_list:
                tools_list.append(item)

    log_debug(f"EXTRACTED TOOLS FROM LAUNCHDARKLY: {tools_list}")
    if tool_configs:
        log_verbose(f" TOOL CONFIGS FROM LAUNCHDARKLY: {tool_configs}")

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


def _json_schema_field_type(field_name: str, field_config: Dict[str, Any]) -> Any:
    """Map a JSON-schema property definition to its corresponding Python type."""
    schema_type = (field_config or {}).get("type")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        items = (field_config or {}).get("items")
        if field_name == "results" or (isinstance(items, dict) and items.get("type") == "object"):
            return List[Dict[str, Any]]
        return List[Any]
    if schema_type == "object":
        return Dict[str, Any]
    return str


def _build_args_schema(
    model_name: str,
    tool_config: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> type[BaseModel]:
    """Build a Pydantic args_schema from a LaunchDarkly JSON-schema object."""
    field_definitions: Dict[str, Any] = {}
    required = set(tool_config.get("required") or [])
    defaults = defaults or {}

    for field_name, raw_field_cfg in (tool_config.get("properties") or {}).items():
        field_cfg = raw_field_cfg if isinstance(raw_field_cfg, dict) else {}
        field_desc = field_cfg.get("description", "")
        field_type = _json_schema_field_type(field_name, field_cfg)
        if field_name in required:
            field_definitions[field_name] = (field_type, Field(description=field_desc))
        else:
            default_val = field_cfg.get("default", defaults.get(field_name, None))
            field_definitions[field_name] = (
                Optional[field_type],
                Field(default=default_val, description=field_desc),
            )

    return create_model(model_name, **field_definitions)


def _create_dynamic_search_v1(tool_config: Dict[str, Any]) -> BaseTool:
    """Create search_v1 tool with LaunchDarkly configuration"""
    from tools_impl.search_v1 import SearchToolV1

    # Create base tool instance
    tool = SearchToolV1()

    if tool_config:
        if tool_config.get('description'):
            object.__setattr__(tool, 'description', tool_config['description'])
        if 'properties' in tool_config:
            log_debug("SEARCH_V1: Applying LaunchDarkly config")
            object.__setattr__(
                tool,
                'args_schema',
                _build_args_schema('DynamicSearchV1Input', tool_config, defaults={'top_k': 5}),
            )

    return tool


def _create_dynamic_search_v2(tool_config: Dict[str, Any]) -> BaseTool:
    """Create search_v2 tool with LaunchDarkly configuration"""

    # Create dynamic input schema based on LaunchDarkly tool definition
    if tool_config and 'properties' in tool_config:
        properties = tool_config['properties']
        log_debug(f"SEARCH_V2: Creating dynamic schema from LaunchDarkly: {properties}")
        DynamicSearchV2Input = _build_args_schema(
            'DynamicSearchV2Input',
            tool_config,
            defaults={'top_k': 3},
        )
    else:
        # Fallback to minimal schema
        log_debug(f"SEARCH_V2: No LaunchDarkly config found, using minimal schema")
        class DynamicSearchV2Input(BaseModel):
            query: str
            top_k: Optional[int] = 3

    configured_description = (
        (tool_config or {}).get('description')
        or "Semantic search through the knowledge base. Use for technical questions and concepts."
    )

    # Create dynamic tool class
    class DynamicSearchToolV2(BaseTool):
        name: str = "search_v2"
        description: str = configured_description
        args_schema: type[BaseModel] = DynamicSearchV2Input

        def _run(self, query: str, top_k: Optional[int] = 3, **kwargs: Any) -> str:
            # Import and delegate to actual implementation
            from tools_impl.search_v2 import SearchToolV2
            actual_tool = SearchToolV2()
            resolved_top_k = 3 if top_k is None else int(top_k)
            return actual_tool._run(query, resolved_top_k, **kwargs)

    return DynamicSearchToolV2()


def _create_dynamic_reranking_tool(tool_config: Dict[str, Any]) -> BaseTool:
    """Create reranking tool with LaunchDarkly configuration"""

    # Create dynamic input schema based on LaunchDarkly tool definition
    if tool_config and 'properties' in tool_config:
        properties = tool_config['properties']
        log_debug(f"RERANKING: Creating dynamic schema from LaunchDarkly: {properties}")
        DynamicRerankingInput = _build_args_schema('DynamicRerankingInput', tool_config)
    else:
        # Fallback to minimal schema matching LaunchDarkly
        log_debug(f"RERANKING: No LaunchDarkly config found, using minimal schema")
        class DynamicRerankingInput(BaseModel):
            query: str
            results: Optional[List[Dict[str, Any]]] = None

    configured_description = (
        (tool_config or {}).get('description')
        or "Rerank search results by relevance. Use after search to improve result ordering."
    )

    # Create dynamic tool class
    class DynamicRerankingTool(BaseTool):
        name: str = "reranking"
        description: str = configured_description
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