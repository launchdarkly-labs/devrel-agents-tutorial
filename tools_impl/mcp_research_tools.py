from langchain.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools
from tools_impl.openalex_auth import OPENALEX_MCP_URL, TOKEN_FILE, openalex_auth
import os
import shutil
import threading
import traceback

# Process-lifetime singleton to prevent repeated MCP server startup
_MCP_SINGLETON = None
# A thread lock, because each initialization runs on its own event loop
_MCP_LOCK = threading.Lock()


def _query_only(search_works: BaseTool, connection: dict) -> BaseTool:
    """OpenAlex search_works takes dozens of optional filters, and models fill in
    every one, which the server rejects. Expose only the query."""
    async def search(query: str) -> str:
        # The OAuth provider reads the token file only once, so give each call a fresh
        # one; reading the file is what refreshes expired tokens.
        connection["auth"] = openalex_auth()
        return await search_works.ainvoke({"query": query, "limit": 5})
    return StructuredTool.from_function(
        coroutine=search,
        name=search_works.name,
        description="Search OpenAlex for scholarly works. Returns titles, authors, years, and citation counts.",
    )

class MCPResearchTools:
    """MCP Research Tools integration using real MCP servers with process lifetime reuse"""

    def __init__(self):
        self.tools = {}

    async def initialize(self):
        """Load tools from the configured research servers, once per process"""
        global _MCP_SINGLETON

        with _MCP_LOCK:
            if _MCP_SINGLETON is not None:
                self.tools = _MCP_SINGLETON.tools
                print(f"🔄 MCP: Reusing singleton with {len(self.tools)} tools")
                return

        print("  MCP: Initializing process-lifetime singleton...")

        server_configs = {}

        # ArXiv MCP Server - auto-discover from PATH (uv tool install arxiv-mcp-server) or ARXIV_MCP_SERVER_PATH
        arxiv_path = os.getenv('ARXIV_MCP_SERVER_PATH') or shutil.which('arxiv-mcp-server')
        if arxiv_path and os.path.exists(arxiv_path):
            server_configs["arxiv"] = {
                "transport": "stdio",
                "command": arxiv_path,
                "args": ["--storage-path", "/tmp/arxiv-papers"]
            }
            print(f"  MCP: ArXiv server configured at {arxiv_path}")

        # OpenAlex MCP Server - only add after running tools_impl/openalex_auth.py
        if TOKEN_FILE.exists():
            server_configs["openalex"] = {
                "transport": "streamable_http",
                "url": OPENALEX_MCP_URL,
                "auth": openalex_auth()
            }
            print("  MCP: OpenAlex server configured")

        if not server_configs:
            return

        # Load tools from each server individually, so one failing server doesn't block the other
        all_loaded = True
        for server_name, config in server_configs.items():
            try:
                server_tools = await load_mcp_tools(None, connection=config)
            except Exception as e:
                all_loaded = False
                print(f" ERROR: Failed to load tools from {server_name}: {e}")
                print(f" TRACEBACK: {traceback.format_exc()}")
                continue

            # Map the MCP tools we use to their LaunchDarkly tool names
            for tool in server_tools:
                if tool.name == "search_papers":
                    self.tools["arxiv_search"] = tool
                elif tool.name == "search_works":
                    self.tools["openalex_search"] = _query_only(tool, config)

        # A server that failed to load is retried on the next request instead of being cached as missing
        if not all_loaded:
            return

        # Store singleton for process lifetime reuse
        with _MCP_LOCK:
            if _MCP_SINGLETON is None:
                _MCP_SINGLETON = self
                print(" MCP: Singleton initialized for process lifetime")
