"""
Support Agent with Dynamic Tool Loading from LaunchDarkly

LANGGRAPH PATTERN: Agent Wrapper with Dynamic Configuration

This agent demonstrates how to:
1. Load tools dynamically from LaunchDarkly AI Config
2. Create React agents with runtime-fetched configurations
3. Implement simple agent wrapper pattern for LangGraph integration

KEY EDUCATIONAL CONCEPT:
Instead of hardcoded tools, this agent's capabilities are entirely controlled
by LaunchDarkly configuration, enabling A/B testing of tool availability.
"""
from typing import List, Any
from .ld_agent_helpers import create_simple_agent_wrapper
from tools_impl.dynamic_tool_factory import create_dynamic_tools_from_launchdarkly
from utils.logger import log_student


def create_support_agent(config, config_manager):
    """
    Create Support Agent with Dynamic LaunchDarkly Tool Loading

    LANGGRAPH INTEGRATION PATTERN:
    This function returns an agent wrapper that integrates with LangGraph
    by exposing an invoke() method that matches LangGraph node expectations.

    DYNAMIC TOOL LOADING WORKFLOW:
    1. Extract tool definitions from LaunchDarkly AI Config
    2. Create actual tool instances using dynamic factory
    3. Create agent wrapper that fetches fresh config on each call
    4. Return wrapper with invoke() method for LangGraph compatibility

    KEY EDUCATIONAL CONCEPTS:
    - Tools are NOT hardcoded - they come from LaunchDarkly configuration
    - Different users can get different tool sets based on targeting rules
    - A/B testing of tool availability is built into the agent design
    - Agent wrapper pattern enables runtime configuration changes

    LAUNCHDARKLY TOOL VARIATIONS:
    - docs-only: ["search_v1"] - Basic search only
    - rag-enabled: ["search_v1", "search_v2", "reranking"] - Full RAG stack
    - research-enhanced: ["search_v1", "search_v2", "reranking", "arxiv_search"] - RAG + MCP
    """

    # STEP 1: Extract tool definitions from LaunchDarkly AI Config
    # This reads the 'tools' parameter from the LaunchDarkly configuration
    # and creates actual executable tool instances
    available_tools = create_dynamic_tools_from_launchdarkly(config)

    # STEP 2: Create agent wrapper with dynamic configuration fetching
    # This wrapper will fetch fresh LaunchDarkly config on each invocation
    # ensuring that configuration changes take effect immediately
    agent_wrapper = create_simple_agent_wrapper(
        config_manager=config_manager,
        config_key="support-agent",      # LaunchDarkly AI Config key
        tools=available_tools            # Tools loaded from configuration
    )

    # STEP 3: Return wrapper with invoke() method for LangGraph integration
    # The wrapper's invoke() method matches LangGraph node function signature
    return agent_wrapper