"""Local defaults when LaunchDarkly is unavailable, and events attributed to the served variation."""
import config_manager
from config_manager import FEEDBACK_POSITIVE_EVENT, FixedConfigManager
from launchdarkly_ai_server.tracking import parse_usage
from tests.fakes import served


async def test_unreachable_launchdarkly_serves_defaults_and_backs_off(monkeypatch):
    attempts = []

    async def unreachable(options):
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
    async def connected(options):
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
        handler_result = await kwargs["handler"]()
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
