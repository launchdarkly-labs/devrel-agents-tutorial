"""Local defaults when LaunchDarkly is unavailable, and events attributed to the served variation."""
import config_manager
from config_manager import FEEDBACK_POSITIVE_EVENT, FixedConfigManager
from launchdarkly_ai_server import init_client, parse_usage, shutdown
from tests.fakes import served


async def test_unreachable_launchdarkly_serves_defaults_and_backs_off(monkeypatch):
    attempts = []

    async def unreachable(options=None):
        attempts.append(options)
        raise RuntimeError("LaunchDarkly client failed to initialize")

    monkeypatch.setattr(config_manager, "init_client", unreachable)
    manager = FixedConfigManager()

    for key in ["supervisor-agent", "support-agent", "security-agent"]:
        config = await manager.get_config("u1", key, {"plan": "free"})
        assert config.from_fallback
        assert config.model_name == "claude-haiku-5-5"
        assert config.variation_key == "fallback"

    # Only the first call waits for LaunchDarkly; the rest serve defaults right away
    assert len(attempts) == 1


async def test_disabled_config_serves_defaults(monkeypatch):
    async def connected(options=None):
        return None

    async def disabled(config_key, context):
        return {"enabled": False, "config": None, "meta": {"enabled": False}}

    monkeypatch.setattr(config_manager, "init_client", connected)
    monkeypatch.setattr(config_manager, "inspect_config", disabled)

    config = await FixedConfigManager().get_config("u1", "support-agent")
    assert config.from_fallback
    assert [tool["name"] for tool in config.parameters["tools"]] == ["search_v1", "search_v2", "reranking"]


def capture_events(monkeypatch):
    events = []
    monkeypatch.setattr(FixedConfigManager, "_track",
                        staticmethod(lambda event, context, data, value: events.append((event, data, value))))
    return events


def test_feedback_is_attributed_to_the_served_variation(monkeypatch):
    events = capture_events(monkeypatch)
    support_config = served("support-agent", variation_key="other-paid")

    assert FixedConfigManager().track_feedback(support_config, {"kind": "user", "key": "u1"}, thumbs_up=True)

    event, data, value = events[0]
    assert event == FEEDBACK_POSITIVE_EVENT
    assert data["variationKey"] == "other-paid"
    assert data["configKey"] == "support-agent"


async def test_cost_event_uses_the_served_variation(monkeypatch):
    events = capture_events(monkeypatch)
    support_config = served("support-agent", variation_key="other-paid")

    async def fake_execute_and_track(**kwargs):
        handler_result = await kwargs["handler"](kwargs["config"], kwargs.get("user_input"), {}, {"ldContext": kwargs["user_context"]}, None)
        assert handler_result["output"] == "answer"
        return {"usage": parse_usage(handler_result["usage"]),
                "track_data": {"configKey": "support-agent", "variationKey": "other-paid"}}

    monkeypatch.setattr(config_manager, "create_handler", lambda provides_for, fn: fn)
    monkeypatch.setattr(config_manager, "execute_and_track", fake_execute_and_track)

    async def model_call():
        return "answer", {"input_tokens": 1000, "output_tokens": 500}

    result = await FixedConfigManager().track(support_config, {"kind": "user", "key": "u1"}, model_call)

    assert result == "answer"
    event, data, value = events[0]
    assert event == "ai_cost_per_request"
    assert data["variationKey"] == "other-paid"
    assert value > 0


async def test_sdk_tool_handlers_emit_tool_call_events_and_render_templates(monkeypatch):
    import agents.ld_agent_helpers as helpers

    class FakeLDClient:
        def __init__(self):
            self.tracked = []

        def track(self, event, context, data, value=1):
            self.tracked.append((event, data, value))

        def flush(self):
            pass

    await shutdown()
    fake_ld = FakeLDClient()
    await init_client(client=fake_ld)
    try:
        tool_spec = {"name": "search_v2", "description": "Search", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}
        support_config = served("support-agent", variation_key="other-paid", tools=[tool_spec])
        support_config.config["instructions"] = "Helping a {{ldContext.plan}} customer."

        async def search_impl(**kwargs):
            return f"hit:{kwargs['query']}"

        seen_prompt = {}

        async def run_turn(tracked_tools, variables):
            seen_prompt["text"] = support_config.render_instructions(variables)
            res = await tracked_tools["search_v2"](query="q-learning")
            return res, f"Final: {res}", {"input_tokens": 20, "output_tokens": 10}

        ctx = {"kind": "user", "key": "u1", "plan": "paid"}
        result = await FixedConfigManager().track(
            support_config, ctx, run_turn, user_input="What is Q-learning?", tool_handlers={"search_v2": search_impl}
        )

        assert result == "hit:q-learning"
        assert seen_prompt["text"] == "Helping a paid customer."
        event_names = [e for e, _, _ in fake_ld.tracked]
        assert "$ld:ai:tool_call" in event_names
        assert "$ld:ai:generation:success" in event_names
        tool_event = next(data for e, data, _ in fake_ld.tracked if e == "$ld:ai:tool_call")
        assert tool_event["toolKey"] == "search_v2"
        assert tool_event["modelKey"] == "Anthropic.claude-haiku-5-5"
        assert "runId" in tool_event

        # Verify create_chat_model forwards model.parameters while stripping attached tools
        forwarded = {}
        monkeypatch.setattr(helpers, "init_chat_model", lambda **kw: forwarded.update(kw) or "llm")
        helpers.create_chat_model("Anthropic", "claude-haiku-5-5", None, {"max_tokens": 512, "tools": [tool_spec]})
        assert forwarded == {"model": "claude-haiku-5-5", "model_provider": "anthropic", "max_tokens": 512}
    finally:
        await shutdown()


def test_flush_traces_uses_public_otel_provider(monkeypatch):
    flushed = []

    class FakeTracerProvider:
        def force_flush(self):
            flushed.append(True)

    monkeypatch.setattr(config_manager.trace, "get_tracer_provider", lambda: FakeTracerProvider())
    manager = FixedConfigManager()
    manager.flush_traces()
    assert flushed == [True]

    # Proxy/no-op provider without force_flush must be a safe no-op
    monkeypatch.setattr(config_manager.trace, "get_tracer_provider", lambda: object())
    manager.flush_traces()

