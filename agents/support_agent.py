"""
Support Agent following LaunchDarkly AI pattern
"""
from typing import List, Any
from .ld_agent_helpers import create_simple_agent_wrapper
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool
from utils.logger import log_student


def create_support_agent(config, config_manager):
    """
    Create support agent following proper LaunchDarkly AI pattern.

    Key insight: Tools don't change per request, but instructions do!
    - Initialize tools once
    - Fetch instructions on each call (LaunchDarkly pattern)
    """
    log_student("🔧 SUPPORT: Creating agent with LaunchDarkly pattern")

    # Get tools from the initial config (tools are stable, instructions are dynamic)

    tools_list = []
    if hasattr(config, 'tools') and config.tools:
        tools_list = list(config.tools)

    # Try to get tools from config dict structure
    try:
        config_dict = config.to_dict()
        if 'model' in config_dict and 'parameters' in config_dict['model'] and 'tools' in config_dict['model']['parameters']:
            tools_data = config_dict['model']['parameters']['tools']
            for tool in tools_data:
                if 'name' in tool and tool['name'] not in tools_list:
                    tools_list.append(tool['name'])
    except:
        pass


    # Initialize available tools list
    available_tools = []

    # Create basic tool instances (skip MCP for now to avoid complexity)
    for tool_name in tools_list:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
        elif tool_name in ["arxiv_search", "semantic_scholar"]:
            # Add MCP tools with simple error handling
            try:
                from tools_impl.mcp_research_tools import get_research_tools
                import asyncio

                # Quick MCP initialization (no complex threading like original)
                try:
                    mcp_tools = asyncio.run(get_research_tools())
                    if mcp_tools:
                        for mcp_tool in mcp_tools:
                            if hasattr(mcp_tool, 'name') and tool_name.replace('_', ' ') in mcp_tool.name.lower():
                                available_tools.append(mcp_tool)
                                break
                except Exception as e:
                    pass
            except ImportError:
                pass

    # Create the agent wrapper that fetches config on each call
    agent_wrapper = create_simple_agent_wrapper(
        config_manager=config_manager,
        config_key="support-agent",
        tools=available_tools
    )

    log_student(f"✅ SUPPORT: Agent created with {len(available_tools)} tools")
    return agent_wrapper