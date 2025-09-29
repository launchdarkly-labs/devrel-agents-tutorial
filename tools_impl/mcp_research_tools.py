from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.sessions import StdioConnection
import asyncio
from typing import List, Optional
import logging
import time
import random
import sys
import os
import subprocess
import io

logger = logging.getLogger(__name__)

# Process-lifetime singleton to prevent repeated MCP server startup
_MCP_SINGLETON = None
_MCP_LOCK = asyncio.Lock()

class MCPResearchTools:
    """MCP Research Tools integration using real MCP servers with process lifetime reuse"""
    
    def __init__(self):
        self.client = None
        self.tools = {}
        self._initialized = False

    def _is_ui_environment(self):
        """Detect if we're in a UI environment that captures stderr"""
        # Only skip MCP if stderr is actually captured or unusable
        try:
            # Test if stderr actually works
            if not hasattr(sys.stderr, 'fileno'):
                return True

            # Try to call fileno() - this will fail in captured environments
            sys.stderr.fileno()

            # Check if stderr is a capturing object
            if 'CapturingStdErr' in str(type(sys.stderr)):
                return True

            # If we get here, stderr works fine
            return False

        except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
            # stderr doesn't work properly
            return True
        
    async def initialize(self):
        """Initialize MCP client with research servers using process lifetime reuse"""
        global _MCP_SINGLETON

        # Check if we're in a problematic environment (UI/Streamlit)
        if self._is_ui_environment():
            print("MCP: Skipping initialization in UI environment (stderr capture detected)")
            self._initialized = True
            return

        async with _MCP_LOCK:
            if _MCP_SINGLETON is not None:
                # Check if singleton has tools before reusing
                if hasattr(_MCP_SINGLETON, 'tools') and _MCP_SINGLETON.tools:
                    # Reuse existing singleton with tools
                    self.client = _MCP_SINGLETON.client
                    self.tools = _MCP_SINGLETON.tools
                    self._initialized = True
                    print(f"MCP: Reusing singleton with {len(self.tools)} tools")
                    return
                else:
                    # Singleton exists but has no tools, clear it and reinitialize
                    print(f"MCP: Singleton has 0 tools, clearing and reinitializing...")
                    _MCP_SINGLETON = None

            print("MCP: Initializing process-lifetime singleton...")

        try:
            # Configure MCP servers for research
            # NOTE: MCP servers can cause initialization timeouts in some environments
            server_configs = {
                # ArXiv MCP Server (Python-based) - RE-ENABLED
                "arxiv": {
                    "command": "/Users/ld_scarlett/.local/bin/arxiv-mcp-server", 
                    "args": ["--storage-path", "/tmp/arxiv-papers"]
                },
                # Semantic Scholar MCP Server (Python-based)
                "semanticscholar": {
                    "command": "python",
                    "args": ["semanticscholar-MCP-Server/semantic_scholar_server.py"]
                }
            }
            
            # Try to initialize with available servers
            available_configs = {}
            for name, config in server_configs.items():
                try:
                    # Test if server is available
                    available_configs[name] = config
                    logger.info(f"MCP server '{name}' configured")
                except Exception as e:
                    logger.warning(f"MCP server '{name}' not available: {e}")
            
            if available_configs:
                # Initialize individual MCP connections and collect tools
                langchain_tools = []
                
                # Load tools from each server individually
                for server_name, config in available_configs.items():
                    try:
                        # Create connection for this server - add transport to config
                        connection_config = {
                            **config,
                            "transport": "stdio"
                        }
                        connection = StdioConnection(connection_config)
                        
                        # Load tools from this server with stderr handling
                        # Fix for CapturingStdErr issue in UI environments
                        original_stderr = sys.stderr
                        try:
                            # If stderr doesn't have fileno, temporarily replace it
                            if not hasattr(sys.stderr, 'fileno') or 'CapturingStdErr' in str(type(sys.stderr)):
                                import io
                                sys.stderr = io.StringIO()

                            server_tools = await load_mcp_tools(None, connection=connection)
                        finally:
                            # Restore original stderr
                            sys.stderr = original_stderr
                        langchain_tools.extend(server_tools)
                        # print(f"DEBUG: Loaded {len(server_tools)} tools from {server_name} MCP server")
                        
                    except Exception as e:
                        print(f" ERROR: Failed to load tools from {server_name}: {e}")
                        import traceback
                        print(f" TRACEBACK: {traceback.format_exc()}")
                        continue
                
                # Organize tools by type - map actual MCP tools to our expected names
                for tool in langchain_tools:
                    tool_name = tool.name.lower()
                    # print(f"DEBUG: Found MCP tool: {tool.name} ({tool.description[:100]}...)")
                    
                    # Map ArXiv tools - use search_papers as the primary tool for arxiv_search
                    if "search_papers" in tool_name or "arxiv" in tool_name:
                        self.tools["arxiv_search"] = tool
                        # Store all ArXiv tools under their original names too
                        self.tools[tool.name] = tool
                    # Map Semantic Scholar tools - use search_semantic_scholar as primary
                    elif "semantic_scholar" in tool_name:
                        if "search_semantic_scholar" in tool_name:
                            self.tools["semantic_scholar"] = tool
                        # Store all Semantic Scholar tools under their original names
                        self.tools[tool.name] = tool
                        
                # print(f"DEBUG: Initialized MCP tools: {list(self.tools.keys())}")
                
                # Store singleton for process lifetime reuse
                async with _MCP_LOCK:
                    if _MCP_SINGLETON is None:
                        _MCP_SINGLETON = self
                        print("MCP: Singleton initialized for process lifetime")
                
        except Exception as e:
            # print(f"DEBUG: Failed to initialize MCP client: {e}")
            self.client = None
        
        self._initialized = True
        # print("DEBUG: MCPResearchTools.initialize() completed")
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a specific MCP tool"""
        return self.tools.get(tool_name)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available MCP tool names"""
        return list(self.tools.keys())
    
    async def close(self):
        """Clean up MCP client"""
        if self.client:
            await self.client.close()


# Simplified for demo - no singleton caching
async def get_mcp_research_tools() -> MCPResearchTools:
    """Create and initialize MCP research tools instance"""
    # print("DEBUG: Creating new MCPResearchTools instance")
    mcp_research_tools = MCPResearchTools()
    # print("DEBUG: Initializing MCP tools...")
    await mcp_research_tools.initialize()
    # print("DEBUG: MCP initialization completed")
    return mcp_research_tools


# MCP-only implementation - no fallback tools
async def get_research_tools() -> List[BaseTool]:
    """Get MCP research tools - requires MCP servers to be installed"""
    # print("DEBUG: get_research_tools called")
    tools = []
    
    try:
        # print("DEBUG: Getting MCP research tools instance")
        mcp_tools = await get_mcp_research_tools()
        available_tools = mcp_tools.get_available_tools()
        # print(f"DEBUG: Available MCP tools: {available_tools}")
        
        # Only return real MCP tools - no fallbacks
        if "arxiv_search" in available_tools:
            tools.append(mcp_tools.get_tool("arxiv_search"))
            print("Added ArXiv MCP tool")
            
        if "semantic_scholar" in available_tools:
            tools.append(mcp_tools.get_tool("semantic_scholar"))
            print("Added Semantic Scholar MCP tool")
        
        if not tools:
            print("No MCP research tools available. Install MCP servers: npm install -g @michaellatman/mcp-server-arxiv")
            
    except Exception as e:
        print(f"MCP tools initialization failed: {e}")
        print("Install MCP servers to enable research tools: npm install -g @michaellatman/mcp-server-arxiv")
    
    # print(f"DEBUG: Returning {len(tools)} MCP tools")
    return tools