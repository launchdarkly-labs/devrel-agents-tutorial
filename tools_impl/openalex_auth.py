"""Sign in to the OpenAlex MCP server.

The OpenAlex MCP server only accepts OAuth, so sign in once with a free
OpenAlex account:

    uv run python tools_impl/openalex_auth.py

Tokens are saved to .openalex_tokens.json and refreshed automatically after that.
"""
import asyncio
import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

OPENALEX_MCP_URL = "https://mcp.openalex.org/mcp"
TOKEN_ENDPOINT = "https://mcp.openalex.org/oauth/token"
TOKEN_FILE = Path(__file__).resolve().parent.parent / ".openalex_tokens.json"
CALLBACK_PORT = 3030


class FileTokenStorage:
    """Keeps the OAuth client registration and tokens in TOKEN_FILE."""

    def _read(self) -> dict:
        return json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else {}

    def _write(self, key: str, value) -> None:
        data = self._read()
        data[key] = value.model_dump(mode="json")
        if key == "tokens":
            data["expires_at"] = time.time() + (value.expires_in or 3600) - 60
        # Created owner-only, so the tokens are never readable by other users
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)  # the mode above only applies when the file is new
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data))

    async def get_tokens(self):
        data = self._read()
        if "tokens" not in data:
            return None
        # The MCP client doesn't know when stored tokens expire, so refresh them here
        if time.time() > data.get("expires_at", 0):
            async with httpx.AsyncClient() as client:
                response = await client.post(TOKEN_ENDPOINT, data={
                    "grant_type": "refresh_token",
                    "refresh_token": data["tokens"]["refresh_token"],
                    "client_id": data["client_info"]["client_id"],
                    "resource": OPENALEX_MCP_URL,
                })
            response.raise_for_status()
            tokens = OAuthToken.model_validate(response.json())
            # A refresh response may omit the refresh token, which means keep using the old one
            tokens.refresh_token = tokens.refresh_token or data["tokens"]["refresh_token"]
            await self.set_tokens(tokens)
            return tokens
        return OAuthToken.model_validate(data["tokens"])

    async def set_tokens(self, tokens) -> None:
        self._write("tokens", tokens)

    async def get_client_info(self):
        info = self._read().get("client_info")
        return OAuthClientInformationFull.model_validate(info) if info else None

    async def set_client_info(self, client_info) -> None:
        self._write("client_info", client_info)


def _wait_for_callback() -> tuple[str, str | None]:
    """Serve one request on the redirect URI and return the code and state."""
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            result["state"] = query.get("state", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Signed in to OpenAlex. You can close this tab.")

        def log_message(self, *args):
            pass

    HTTPServer(("localhost", CALLBACK_PORT), Handler).handle_request()
    return result["code"], result["state"]


def openalex_auth(interactive: bool = False) -> OAuthClientProvider:
    """OAuth for the OpenAlex MCP connection. Only the sign-in script opens a browser."""

    async def redirect(authorization_url: str) -> None:
        if not interactive:
            raise RuntimeError("OpenAlex sign-in required: run `uv run python tools_impl/openalex_auth.py`")
        print(f"Opening {authorization_url}")
        webbrowser.open(authorization_url)

    async def callback() -> tuple[str, str | None]:
        return await asyncio.to_thread(_wait_for_callback)

    return OAuthClientProvider(
        server_url=OPENALEX_MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="LaunchDarkly multi-agent tutorial",
            redirect_uris=[f"http://localhost:{CALLBACK_PORT}/callback"],
            token_endpoint_auth_method="none",
        ),
        storage=FileTokenStorage(),
        redirect_handler=redirect,
        callback_handler=callback,
    )


async def main():
    from langchain_mcp_adapters.tools import load_mcp_tools

    tools = await load_mcp_tools(None, connection={
        "transport": "streamable_http", "url": OPENALEX_MCP_URL, "auth": openalex_auth(interactive=True),
    })
    print(f"Signed in. OpenAlex tools: {[tool.name for tool in tools]}")


if __name__ == "__main__":
    asyncio.run(main())
