"""
Tool implementations for LaunchDarkly AI Config CI/CD Direct Evaluator

This file provides simple function wrappers for the Direct evaluator to use
when testing AI configs. These functions delegate to the actual LangChain
tool implementations in tools_impl/.

The Direct evaluator loads these functions and converts them to provider-specific
formats (OpenAI function calling, Anthropic tools, Gemini functions, etc.).

Convention: Function signatures and docstrings are introspected to generate
JSON schemas automatically. Use type hints for proper schema generation.
"""

import os
from typing import List, Dict, Any, Optional


def search_v1(query: str) -> str:
    """
    Basic keyword-based search through enterprise documentation.

    Performs simple keyword matching across documentation chunks.
    Useful for quick lookups when you know specific terms.

    Args:
        query: Search query to find relevant documentation

    Returns:
        Formatted string with matching text chunks
    """
    try:
        from tools_impl.search_v1 import SearchToolV1
        tool = SearchToolV1()
        return tool._run(query)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in search_v1: {type(e).__name__}: {str(e)}\n{error_details}")
        return f"Search error: {type(e).__name__}: {str(e)}. If this persists, ensure vector embeddings are initialized with 'uv run initialize_embeddings.py'"


def search_v2(query: str, top_k: int = 3) -> str:
    """
    Advanced semantic search using vector embeddings.

    Uses vector similarity to find semantically related content,
    even when exact keywords don't match. More powerful than keyword search.

    Args:
        query: Search query for semantic matching
        top_k: Number of results to return (default: 3, max: 20)

    Returns:
        Formatted string with semantically relevant documents and similarity scores
    """
    try:
        from tools_impl.search_v2 import SearchToolV2
        tool = SearchToolV2()
        # Clamp top_k for safety
        top_k = max(1, min(int(top_k), 20))
        return tool._run(query, top_k)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in search_v2: {type(e).__name__}: {str(e)}\n{error_details}")
        return f"Search error: {type(e).__name__}: {str(e)}. If this persists, ensure vector embeddings are initialized with 'uv run initialize_embeddings.py'"


def reranking(query: str, results: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Reorders search results by relevance using BM25 algorithm.

    Takes results from search_v2 and reranks them using BM25 scoring
    for better relevance. Should be used after search_v2.

    Args:
        query: Original search query
        results: List of search result items from search_v2 with 'text', 'score', 'metadata' fields

    Returns:
        BM25-reranked results with scores
    """
    try:
        from tools_impl.reranking import RerankingTool
        tool = RerankingTool()
        return tool._run(query, results)
    except Exception as e:
        return f"Reranking error: {str(e)}"


def arxiv_search(query: str, max_results: int = 5) -> str:
    """
    Search academic papers from ArXiv database.

    MCP tool that searches the ArXiv preprint repository for academic papers.
    Requires arxiv-mcp-server to be installed. Disabled in CI safe mode.

    Args:
        query: Academic search query
        max_results: Maximum number of papers to return (default: 5)

    Returns:
        Formatted string with ArXiv paper results including titles, authors, and abstracts
    """
    # Check if CI_SAFE_MODE is enabled (network-dependent tools disabled)
    if os.getenv("CI_SAFE_MODE", "").lower() in {"1", "true", "yes"}:
        return "ArXiv search is disabled in CI safe mode (network-dependent MCP tool)"

    try:
        from tools_impl.dynamic_tool_factory import _create_dynamic_mcp_tool
        tool = _create_dynamic_mcp_tool("arxiv_search", {})
        if tool is None:
            return "ArXiv MCP tool not available. Install with: uv tool install arxiv-mcp-server"
        return tool._run(query=query, max_results=max_results)
    except Exception as e:
        return f"ArXiv search error: {str(e)}"


def openalex_search(query: str) -> str:
    """
    Search OpenAlex for scholarly works and citation counts.

    MCP tool that searches the OpenAlex catalog of papers, books, and datasets.
    Requires a one-time sign-in with tools_impl/openalex_auth.py. Disabled in CI safe mode.

    Args:
        query: Academic research query

    Returns:
        Formatted string with OpenAlex results including citation counts
    """
    # Check if CI_SAFE_MODE is enabled (network-dependent tools disabled)
    if os.getenv("CI_SAFE_MODE", "").lower() in {"1", "true", "yes"}:
        return "OpenAlex search is disabled in CI safe mode (network-dependent MCP tool)"

    try:
        from tools_impl.dynamic_tool_factory import _create_dynamic_mcp_tool
        tool = _create_dynamic_mcp_tool("openalex_search", {})
        if tool is None:
            return "OpenAlex MCP tool not available. Sign in with: uv run python tools_impl/openalex_auth.py"
        return tool._run(query=query)
    except Exception as e:
        return f"OpenAlex search error: {str(e)}"


# Tool metadata for LaunchDarkly AI Config registration
# This helps the Direct evaluator discover available tools
__all__ = [
    "search_v1",
    "search_v2",
    "reranking",
    "arxiv_search",
    "openalex_search"
]
