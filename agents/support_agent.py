"""
Support Agent following LaunchDarkly AI pattern
"""
from typing import List, Any
from .ld_agent_helpers import create_simple_agent_wrapper
from tools_impl.dynamic_tool_factory import create_dynamic_tools_from_launchdarkly
from utils.logger import log_student


def create_support_agent(config, config_manager):
    """
    Create support agent following proper LaunchDarkly AI pattern.

    Key insight: Tools are loaded dynamically from LaunchDarkly configuration!
    - Extract tool schemas, descriptions, and parameters from LaunchDarkly
    - Create tool instances with proper configuration
    - No hardcoded tool definitions
    """

    # Use dynamic tool factory to create tools from LaunchDarkly configuration
    available_tools = create_dynamic_tools_from_launchdarkly(config)

    # Create the agent wrapper that fetches config on each call
    agent_wrapper = create_simple_agent_wrapper(
        config_manager=config_manager,
        config_key="support-agent",
        tools=available_tools
    )

    return agent_wrapper