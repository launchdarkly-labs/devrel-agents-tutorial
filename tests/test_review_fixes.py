"""Unit tests covering all 6 review items on devrel-agents-tutorial#30."""
import asyncio
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("LD_SDK_KEY", "sdk-test-key")
os.environ.setdefault("LD_API_KEY", "api-test-key")
os.environ.setdefault("AUTH_METHOD", "api-key")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


async def test_dynamic_tool_factory_reads_top_level_tools_dict_schema_and_invokes_all_tools(monkeypatch):
    import tools_impl.search_v1 as search_v1_mod
    import tools_impl.search_v2 as search_v2_mod
    from agents.ld_agent_helpers import ToolCallCounter, wrap_tool_with_counter
    from tools_impl.dynamic_tool_factory import (
        create_dynamic_tools_from_launchdarkly,
        extract_tool_configs_from_launchdarkly,
    )

    class FakeVectorStore:
        documents = [
            "Umbra offers a 30-day refund policy on Pro and Team plans.",
            "Serverless functions support 15-minute maximum timeout limits.",
            "Deployments run across US, EU, and APAC edge regions.",
        ]

        def exists(self):
            return True

        def search(self, query: str, top_k: int = 3):
            return [(doc, 0.85, {"idx": idx}) for idx, doc in enumerate(self.documents[:top_k])]

    monkeypatch.setattr(search_v1_mod, "VectorStore", FakeVectorStore)
    monkeypatch.setattr(search_v2_mod, "_get_vector_store", lambda: FakeVectorStore())
    search_v2_mod._cached_search.cache_clear()

    # Exact bootstrap schemas for search_v1 (top_k: number optional) + extra custom field on search_v2
    served_config = {
        "instructions": "Answer using tools.",
        "model": {"name": "claude-sonnet-5-5"},
        "provider": {"name": "Anthropic"},
        "tools": {
            "search_v1": {
                "name": "search_v1",
                "type": "function",
                "description": "Custom LD keyword search description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query for keyword matching"},
                        "top_k": {"type": "integer", "description": "Number of results to return"},
                    },
                    "required": ["query"],
                },
            },
            "search_v2": {
                "name": "search_v2",
                "type": "function",
                "description": "Custom LD semantic search description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "LD query field"},
                        "top_k": {"type": "integer", "description": "LD top_k field"},
                        "category": {"type": "string", "description": "Optional category filter"},
                    },
                    "required": ["query"],
                },
            },
            "reranking": {
                "name": "reranking",
                "type": "function",
                "description": "Custom LD reranking description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query to rank against"},
                        "results": {"type": "array", "description": "Candidate results"},
                    },
                    "required": ["query"],
                },
            },
        },
    }

    tools_list, tool_configs = extract_tool_configs_from_launchdarkly(served_config)
    assert tools_list == ["search_v1", "search_v2", "reranking"]
    assert "properties" in tool_configs["search_v2"]
    assert "category" in tool_configs["search_v2"]["properties"]

    tools = create_dynamic_tools_from_launchdarkly(served_config)
    v1_tool = next(t for t in tools if t.name == "search_v1")
    v2_tool = next(t for t in tools if t.name == "search_v2")
    rerank_tool = next(t for t in tools if t.name == "reranking")

    assert v1_tool.description == "Custom LD keyword search description"
    assert v2_tool.description == "Custom LD semantic search description"
    assert "category" in v2_tool.args_schema.model_fields
    assert v2_tool.args_schema.model_fields["query"].description == "LD query field"
    assert rerank_tool.description == "Custom LD reranking description"

    # Exercise both direct BaseTool.invoke/ainvoke and GenericAgent's wrap_tool_with_counter wrapper
    counter = ToolCallCounter(max_calls=20)
    wrapped = {t.name: wrap_tool_with_counter(t, counter) for t in tools}

    # search_v1: without top_k, with numeric top_k, and with explicit null top_k
    assert "30-day refund" in v1_tool.invoke({"query": "refund"})
    assert "30-day refund" in wrapped["search_v1"].invoke({"query": "refund"})
    assert "30-day refund" in await wrapped["search_v1"].ainvoke({"query": "refund", "top_k": 2})
    assert "30-day refund" in await wrapped["search_v1"].ainvoke({"query": "refund", "top_k": None})

    # search_v2: without top_k/category, with extra schema field, and with explicit nulls
    assert "Found 3 relevant document(s)" in v2_tool.invoke({"query": "refund"})
    assert "Found 2 relevant document(s)" in wrapped["search_v2"].invoke(
        {"query": "refund", "top_k": 2, "category": "billing"}
    )
    assert "Found 3 relevant document(s)" in await wrapped["search_v2"].ainvoke(
        {"query": "refund", "top_k": None, "category": None}
    )

    # reranking: with results list, omitted results, and explicit null results (matching bootstrap schema)
    from bootstrap.create_configs import MultiAgentBootstrap
    from unittest.mock import patch, MagicMock

    captured_payloads = {}
    fake_resp = MagicMock(status_code=201)
    fake_resp.json.return_value = {"key": "ok"}
    with patch("bootstrap.create_configs.http.post", side_effect=lambda _u, headers=None, json=None, timeout=None: (captured_payloads.setdefault(json["key"], json["schema"]), fake_resp)[1]), patch("bootstrap.create_configs.time.sleep"):
        bs = MultiAgentBootstrap("fake-key")
        for key in ("search_v1", "search_v2", "reranking"):
            bs.create_tool("proj", {"key": key, "name": key, "description": key})
    assert captured_payloads["reranking"]["required"] == ["query"]
    assert captured_payloads["search_v1"]["properties"]["top_k"]["type"] == "integer"
    assert captured_payloads["search_v2"]["properties"]["top_k"]["type"] == "integer"

    sample_results = [{"text": "Refunds within 30 days", "score": 0.8}, {"text": "Edge regions", "score": 0.7}]
    assert "BM25 reranked results" in rerank_tool.invoke({"query": "refund", "results": sample_results})
    assert "BM25 reranked results" in await wrapped["reranking"].ainvoke(
        {"query": "refund", "results": sample_results}
    )
    assert "No search results found" in wrapped["reranking"].invoke({"query": "refund"})
    assert "No search results found" in wrapped["reranking"].invoke({"query": "refund", "results": None})


def test_graph_tracker_uses_make_track_data_for_node_and_graph_variation(monkeypatch):
    import config_manager
    from config_manager import GraphTracker

    tracked = []

    class FakeClient:
        def track(self, event, context, data, value=1):
            tracked.append((event, data, value))

    monkeypatch.setattr(config_manager, "get_client", lambda: FakeClient())

    tracker = GraphTracker(
        "chatbot-flow",
        {"kind": "user", "key": "u1", "plan": "paid"},
        meta={"variationKey": "default-flow", "version": 3},
    )
    supervisor_node = SimpleNamespace(
        key="supervisor-agent",
        config={"model": {"name": "gpt-6-luna"}, "provider": {"name": "OpenAI"}},
        meta={"variationKey": "supervisor-v2", "version": 4, "modelKey": "OpenAI.gpt-6-luna", "modelVersion": 1},
    )
    support_node = SimpleNamespace(
        key="support-agent",
        config={"model": {"name": "claude-sonnet-5-5"}, "provider": {"name": "Anthropic"}},
        meta={"variationKey": "eu-paid", "version": 7},
    )

    tracker.track_node_invocation(supervisor_node)
    tracker.track_handoff_success("supervisor-agent", "support-agent")
    tracker.track_node_invocation(support_node)
    tracker.track_invocation_success()

    node_events = [data for evt, data, _ in tracked if evt == "$ld:ai:graph:node"]
    assert len(node_events) == 2
    assert node_events[0]["configKey"] == "supervisor-agent"
    assert node_events[0]["variationKey"] == "supervisor-v2"
    assert node_events[0]["version"] == 4
    assert node_events[0]["modelName"] == "gpt-6-luna"
    assert node_events[0]["providerName"] == "OpenAI"
    assert node_events[0]["modelKey"] == "OpenAI.gpt-6-luna"
    assert node_events[0]["graphKey"] == "chatbot-flow"
    assert node_events[0]["nodeKey"] == "supervisor-agent"
    assert node_events[0]["index"] == 0

    assert node_events[1]["configKey"] == "support-agent"
    assert node_events[1]["variationKey"] == "eu-paid"
    assert node_events[1]["version"] == 7
    assert node_events[1]["nodeKey"] == "support-agent"
    assert node_events[1]["index"] == 1

    graph_success = next(data for evt, data, _ in tracked if evt == "$ld:ai:graph:invocation_success")
    assert graph_success["configKey"] == "chatbot-flow"
    assert graph_success["variationKey"] == "default-flow"
    assert graph_success["version"] == 3


async def test_feedback_uses_served_variation_without_reevaluating_and_rejects_empty(monkeypatch):
    import config_manager
    from api.models import AgentConfig, FeedbackRequest
    from config_manager import FEEDBACK_EVENTS, FixedConfigManager

    # Build a manager without opening a real LaunchDarkly stream
    manager = object.__new__(FixedConfigManager)
    tracked = []

    class FakeLDClient:
        def track(self, event, context, data, value=1):
            tracked.append((event, context, data, value))

        def flush(self):
            pass

    manager.ld_client = FakeLDClient()

    async def noop_ensure():
        return None

    inspect_calls = []

    async def fake_inspect(config_key, context):
        inspect_calls.append((config_key, context))
        return {"enabled": False, "config": None, "meta": None}

    monkeypatch.setattr(FixedConfigManager, "_initialize_launchdarkly_client", lambda self: setattr(self, "ld_client", FakeLDClient()))
    monkeypatch.setattr(manager, "_ensure_ai_client", noop_ensure)
    monkeypatch.setattr(config_manager, "inspect_config", fake_inspect)

    # 1. Served variation from agent_configurations attributes directly without calling inspect_config
    from api.main import _resolve_served_variation

    req = FeedbackRequest(
        user_id="eu-paid-user",
        message_id="msg_1",
        user_query="How do regions work?",
        ai_response="Here are the regions.",
        feedback="positive",
        variation_key="agent-graph",
        model="multi-agent",
        tool_calls=["search_v2"],
        source="real_user",
        user_context={"country": "DE", "plan": "paid"},
        agent_configurations=[
            AgentConfig(agent_name="supervisor-agent", variation_key="sup-default", version=1, model="gpt-6-luna", tools=[]),
            AgentConfig(agent_name="support-agent", variation_key="eu-paid", version=5, model="claude-sonnet-5-5", tools=["search_v2"]),
        ],
    )
    served_cfg, served_var, served_ver = _resolve_served_variation(req, "support-agent")
    assert (served_cfg, served_var, served_ver) == ("support-agent", "eu-paid", 5)

    ctx = manager.build_context(req.user_id, req.user_context)
    ok = await manager.track_feedback(ctx, served_cfg, thumbs_up=True, variation_key=served_var, version=served_ver)
    assert ok is True
    assert inspect_calls == []
    event, _, data, value = tracked[0]
    assert event == FEEDBACK_EVENTS[True]
    assert data == {"configKey": "support-agent", "variationKey": "eu-paid", "version": 5}
    assert value == 1

    # 2. Custom terminal node (no support-agent in agent_configurations) keeps configKey and variationKey aligned
    custom_terminal_req = req.model_copy(
        update={
            "agent_configurations": [
                AgentConfig(agent_name="supervisor-agent", variation_key="sup-default", version=1, model="gpt-6-luna", tools=[]),
                AgentConfig(agent_name="billing-specialist", variation_key="billing-v2", version=3, model="claude-sonnet-5-5", tools=[]),
            ]
        }
    )
    term_cfg, term_var, term_ver = _resolve_served_variation(custom_terminal_req, "support-agent")
    assert (term_cfg, term_var, term_ver) == ("billing-specialist", "billing-v2", 3)
    ok_term = await manager.track_feedback(ctx, term_cfg, thumbs_up=True, variation_key=term_var, version=term_ver)
    assert ok_term is True
    assert tracked[1][2] == {"configKey": "billing-specialist", "variationKey": "billing-v2", "version": 3}

    # 3. Missing variation + failed inspect_config returns False instead of emitting empty variationKey
    ok_missing = await manager.track_feedback(ctx, "support-agent", thumbs_up=False, variation_key=None)
    assert ok_missing is False
    assert len(tracked) == 2

    # 4. config_manager uses only public root launchdarkly_ai_server exports
    cfg_src = (REPO_ROOT / "config_manager.py").read_text()
    assert "launchdarkly_ai_server.tracking" not in cfg_src


async def test_rate_limiter_uses_asyncio_sleep_without_blocking_event_loop(monkeypatch):
    import agents.ld_agent_helpers as helpers

    slept = []

    async def fake_async_sleep(delay):
        slept.append(delay)

    def forbidden_blocking_sleep(_delay):
        raise AssertionError("time.sleep must not be called on the async event loop")

    monkeypatch.setattr(helpers.asyncio, "sleep", fake_async_sleep)
    monkeypatch.setattr(helpers.time, "sleep", forbidden_blocking_sleep)
    helpers._last_llm_call_time = time.monotonic()

    await asyncio.gather(helpers._rate_limit_llm_call(), helpers._rate_limit_llm_call())
    assert len(slept) == 2
    assert slept[1] > slept[0]


def test_update_variation_preserves_model_custom_parameters(monkeypatch):
    import bootstrap.create_configs as create_configs

    patched = []

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"_id": "var-123"}

    monkeypatch.setattr(create_configs.http, "patch", lambda url, headers, json, timeout: patched.append(json) or FakeResp())
    monkeypatch.setattr(create_configs.time, "sleep", lambda _s: None)

    boot = create_configs.MultiAgentBootstrap("api-test-key")
    boot.overwrite = True
    monkeypatch.setattr(boot, "list_variations", lambda _proj, _cfg: [{"key": "eu-paid", "_id": "var-123"}])

    boot.update_variation(
        "multi-agent-chatbot",
        "support-agent",
        {
            "key": "eu-paid",
            "instructions": "Use search_v2.",
            "tools": ["search_v2"],
            "modelConfig": {"modelId": "Anthropic.claude-sonnet-5-5"},
            "customParameters": {"max_tool_calls": 6},
        },
    )

    assert patched[0]["model"] == {"custom": {"max_tool_calls": 6}}
    assert patched[0]["modelConfigKey"] == "Anthropic.claude-sonnet-5-5"


def test_readme_does_not_reference_deleted_agent_registry():
    readme = (REPO_ROOT / "README.md").read_text()
    assert "AGENT_REGISTRY" not in readme
    assert "create_generic_agent" in readme
