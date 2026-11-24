"""OpenAlex tokens refresh from the token file, without a real sign-in or network."""
import json
import stat
import time

import tools_impl.mcp_research_tools as mcp_tools
import tools_impl.openalex_auth as openalex_auth

STORED = {
    "client_info": {"client_id": "test-client", "redirect_uris": ["http://localhost:3030/callback"]},
    "tokens": {"access_token": "old-access", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "old-refresh"},
}


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeHttpClient:
    """Stands in for httpx.AsyncClient and records the refresh request."""
    requests = []
    response = {"access_token": "new-access", "token_type": "Bearer", "expires_in": 3600}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, data):
        FakeHttpClient.requests.append(data)
        return FakeResponse(FakeHttpClient.response)


def token_file(tmp_path, monkeypatch, expires_at):
    path = tmp_path / "openalex_tokens.json"
    path.write_text(json.dumps({**STORED, "expires_at": expires_at}))
    monkeypatch.setattr(openalex_auth, "TOKEN_FILE", path)
    monkeypatch.setattr(openalex_auth.httpx, "AsyncClient", FakeHttpClient)
    FakeHttpClient.requests = []
    return path


async def test_expired_tokens_are_refreshed_and_keep_the_refresh_token(tmp_path, monkeypatch):
    path = token_file(tmp_path, monkeypatch, expires_at=time.time() - 10)

    tokens = await openalex_auth.FileTokenStorage().get_tokens()

    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "old-refresh"
    assert FakeHttpClient.requests[0]["refresh_token"] == "old-refresh"
    saved = json.loads(path.read_text())
    assert saved["tokens"]["refresh_token"] == "old-refresh"
    assert saved["expires_at"] > time.time()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def test_valid_tokens_are_used_without_a_refresh(tmp_path, monkeypatch):
    token_file(tmp_path, monkeypatch, expires_at=time.time() + 600)

    tokens = await openalex_auth.FileTokenStorage().get_tokens()

    assert tokens.access_token == "old-access"
    assert FakeHttpClient.requests == []


async def test_each_search_gets_a_fresh_oauth_provider():
    class FakeSearchWorks:
        name = "search_works"

        def __init__(self, connection):
            self.connection = connection
            self.auth_per_call = []

        async def ainvoke(self, args):
            self.auth_per_call.append(self.connection["auth"])
            return f"works about {args['query']}"

    connection = {"transport": "streamable_http", "url": openalex_auth.OPENALEX_MCP_URL, "auth": None}
    search_works = FakeSearchWorks(connection)
    tool = mcp_tools._query_only(search_works, connection)

    assert await tool.ainvoke({"query": "reinforcement learning"}) == "works about reinforcement learning"
    await tool.ainvoke({"query": "q-learning"})

    first, second = search_works.auth_per_call
    assert first is not second
