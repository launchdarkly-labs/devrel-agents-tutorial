"""max_tool_calls from LaunchDarkly stops the support agent at the limit."""
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

import agents.ld_agent_helpers as helpers
from tests.fakes import FakeConfigManager, served


class SearchInput(BaseModel):
    query: str


class CountingSearch(BaseTool):
    name: str = "search_v2"
    description: str = "Semantic search using vector embeddings"
    args_schema: type[BaseModel] = SearchInput
    calls: int = 0

    def _run(self, query: str) -> str:
        self.calls += 1
        return f"Result for {query}"


class ToolHappyModel(GenericFakeChatModel):
    """A model that asks for one more search every turn."""

    def bind_tools(self, tools, **kwargs):
        return self


def search_request(n):
    return AIMessage(content="", tool_calls=[{"name": "search_v2", "args": {"query": f"q{n}"}, "id": f"call_{n}"}])


async def test_agent_stops_at_max_tool_calls(monkeypatch):
    model = ToolHappyModel(messages=iter([search_request(n) for n in range(10)]))
    monkeypatch.setattr(helpers, "create_chat_model", lambda *args: model)

    search = CountingSearch()
    config_manager = FakeConfigManager({"support-agent": served("support-agent", custom={"max_tool_calls": 2})})
    agent = helpers.create_simple_agent_wrapper(config_manager, "support-agent", [search])

    result = await agent.ainvoke({"user_input": "Research everything", "user_id": "u1"})

    assert search.calls == 2
    assert result["response"].startswith("I've reached the tool call limit for this request.")


def test_other_tool_errors_go_back_to_the_model():
    assert "boom" in helpers._tool_error_message(ValueError("boom"))
