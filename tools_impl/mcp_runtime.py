from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Optional: if MCP uses httpx/aiohttp, wire a shared client into MCPResearchTools
try:
    import httpx
except ImportError:
    httpx = None

class _LoopRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="mcp-loop", daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def call(self, coro, timeout: Optional[float] = None):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout)

    @property
    def loop(self):
        return self._loop

class MCPRuntime:
    """Process-wide MCP runtime: one loop, one MCP client, reusable tools."""
    _instance: Optional["MCPRuntime"] = None
    _lock = threading.Lock()

    def __init__(self):
        from tools_impl.mcp_research_tools import MCPResearchTools  # local import

        logger.info(" Initializing process-wide MCP runtime...")
        self.loop_runner = _LoopRunner()

        # Optional shared HTTP client to pass into MCPResearchTools if supported.
        shared_http: Optional[Any] = None
        if httpx is not None:
            try:
                shared_http = httpx.AsyncClient(
                    # Skip http2 to avoid dependency issues
                    limits=httpx.Limits(max_keepalive_connections=16, max_connections=64),
                    timeout=httpx.Timeout(30.0, connect=10.0),
                )
                logger.info(" Created shared HTTP client for connection pooling")
            except Exception as e:
                logger.warning(" Could not create shared HTTP client: %s", e)
                shared_http = None

        async def _init():
            try:
                # Try to pass shared HTTP client if MCPResearchTools supports it
                try:
                    client = MCPResearchTools(http_client=shared_http) if shared_http else MCPResearchTools()
                except TypeError:
                    # Fallback if MCPResearchTools doesn't accept http_client parameter
                    client = MCPResearchTools()
                
                await client.initialize()
                logger.info(" MCP client initialized successfully")
                return client
            except Exception as e:
                logger.error(" Failed to initialize MCP client: %s", e)
                raise

        try:
            self.client = self.loop_runner.call(_init(), timeout=60)
            self.tools: Dict[str, Any] = getattr(self.client, "tools", {}) or {}
            logger.info(" MCPRuntime initialized with %d tools: %s", len(self.tools), list(self.tools.keys()))
        except Exception as e:
            logger.error(" MCPRuntime initialization failed: %s", e)
            self.client = None
            self.tools = {}

    @classmethod
    def instance(cls) -> "MCPRuntime":
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                cls._instance = MCPRuntime()
        return cls._instance