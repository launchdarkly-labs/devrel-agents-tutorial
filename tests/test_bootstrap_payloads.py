"""The bootstrap scripts send custom parameters where LaunchDarkly stores them: model.custom."""
from pathlib import Path

import yaml

import bootstrap.create_configs as create_configs
import bootstrap.tutorial_3_experiment_variations as tutorial_3


class FakeResponse:
    status_code = 201
    text = ""

    def json(self):
        return {}


def manifest_variation(config_key, variation_key):
    manifest = yaml.safe_load(Path("bootstrap/ai_config_manifest.yaml").read_text())
    config = next(c for c in manifest["project"]["ai_config"] if c["key"] == config_key)
    return next(v for v in config["variations"] if v["key"] == variation_key)


def test_part_2_variations_send_max_tool_calls(monkeypatch):
    sent = []
    monkeypatch.setattr(create_configs.http, "post", lambda url, headers, json, timeout: sent.append(json) or FakeResponse())
    monkeypatch.setattr(create_configs.time, "sleep", lambda seconds: None)

    bootstrap = create_configs.MultiAgentBootstrap("api-test-key")
    bootstrap.create_variation("multi-agent-chatbot", "support-agent", manifest_variation("support-agent", "eu-paid"))

    payload = sent[0]
    assert payload["modelConfigKey"] == "Anthropic.claude-sonnet-5-5"
    assert payload["model"]["custom"]["max_tool_calls"] == 20


def test_part_3_variation_sends_max_tool_calls(monkeypatch):
    sent = []
    monkeypatch.setattr(tutorial_3.requests, "post", lambda url, json, headers, timeout: sent.append(json) or FakeResponse())
    monkeypatch.setattr(tutorial_3.time, "sleep", lambda seconds: None)

    assert tutorial_3.Tutorial3VariationBootstrap().create_premium_model_variations()

    payload = sent[0]
    assert payload["modelConfigKey"] == "Anthropic.claude-opus-5-5"
    assert payload["model"] == {"custom": {"max_tool_calls": 10}}
    assert "max_tool_calls" not in payload
