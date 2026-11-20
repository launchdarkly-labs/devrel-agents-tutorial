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


def test_dynamic_tool_factory_reads_top_level_tools_dict_schema_and_description():
    from tools_impl.dynamic_tool_factory import (
        create_dynamic_tools_from_launchdarkly,
        extract_tool_configs_from_launchdarkly,
    )

    served_config = {
        "instructions": "Answer using tools.",
        "model": {"name": "claude-sonnet-5-5"},
        "provider": {"name": "Anthropic"},
        "tools": {
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
    assert tools_list == ["search_v2", "reranking"]
    assert "properties" in tool_configs["search_v2"]
    assert "category" in tool_configs["search_v2"]["properties"]

    tools = create_dynamic_tools_from_launchdarkly(served_config)
    search_tool = next(t for t in tools if t.name == "search_v2")
    rerank_tool = next(t for t in tools if t.name == "reranking")

    assert search_tool.description == "Custom LD semantic search description"
    assert "category" in search_tool.args_schema.model_fields
    assert search_tool.args_schema.model_fields["query"].description == "LD query field"
    assert rerank_tool.description == "Custom LD reranking description"


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
    served_var, served_ver = _resolve_served_variation(req, "support-agent")
    assert (served_var, served_ver) == ("eu-paid", 5)

    ctx = manager.build_context(req.user_id, req.user_context)
    ok = await manager.track_feedback(ctx, "support-agent", thumbs_up=True, variation_key=served_var, version=served_ver)
    assert ok is True
    assert inspect_calls == []
    event, _, data, value = tracked[0]
    assert event == FEEDBACK_EVENTS[True]
    assert data == {"configKey": "support-agent", "variationKey": "eu-paid", "version": 5}
    assert value == 1

    # 2. Missing variation + failed inspect_config returns False instead of emitting empty variationKey
    ok_missing = await manager.track_feedback(ctx, "support-agent", thumbs_up=False, variation_key=None)
    assert ok_missing is False
    assert len(tracked) == 1


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
