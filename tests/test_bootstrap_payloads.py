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


def test_unmapped_provider_fallback_uses_canonical_provider_casing(monkeypatch):
    sent = []
    monkeypatch.setattr(create_configs.http, "post", lambda url, headers, json, timeout: sent.append(json) or FakeResponse())
    monkeypatch.setattr(create_configs.time, "sleep", lambda seconds: None)

    bootstrap = create_configs.MultiAgentBootstrap("api-test-key")
    bootstrap.create_variation(
        "multi-agent-chatbot",
        "support-agent",
        {
            "key": "custom-openai",
            "instructions": "Help the user.",
            "modelConfig": {"provider": "openai", "modelId": "gpt-custom-preview"},
            "tools": [],
        },
    )

    payload = sent[0]
    assert payload["modelName"] == "gpt-custom-preview"
    assert payload["provider"] == {"name": "OpenAI"}


def test_part_3_free_mistral_option_and_provider_casing(monkeypatch):
    sent = []
    monkeypatch.setattr(tutorial_3.requests, "post", lambda url, json, headers, timeout: sent.append(json) or FakeResponse())
    monkeypatch.setattr(tutorial_3.time, "sleep", lambda seconds: None)

    boot = tutorial_3.Tutorial3VariationBootstrap()
    assert boot._create_variations(
        "support-agent",
        [
            {
                "key": "mistral-free",
                "name": "Mistral Free",
                "instructions": "Help the user.",
                "model": {"name": "mistral-small-latest", "provider": "mistral"},
                "tools": ["search_v1"],
                "customParameters": {"max_tool_calls": 10},
            },
            {
                "key": "mistral-custom",
                "name": "Mistral Custom",
                "instructions": "Help the user.",
                "model": {"name": "mistral-custom-preview", "provider": "mistral"},
                "tools": ["search_v1"],
                "customParameters": {"max_tool_calls": 10},
            },
        ],
    )

    assert sent[0]["modelConfigKey"] == "Mistral.mistral-small-latest"
    assert sent[1]["modelName"] == "mistral-custom-preview"
    assert sent[1]["provider"] == {"name": "Mistral"}


def test_dynamic_tools_accept_integer_top_k_and_string_rerank_results(monkeypatch):
    from tools_impl.dynamic_tool_factory import _create_dynamic_reranking_tool, _create_dynamic_search_v2
    import tools_impl.search_v2 as search_v2_mod

    seen = {}

    def fake_run(self, query, top_k=3, **kwargs):
        seen["top_k"] = top_k
        return f"hit:{query}:{top_k}"

    monkeypatch.setattr(search_v2_mod.SearchToolV2, "_run", fake_run)

    search_tool = _create_dynamic_search_v2(
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        }
    )
    assert search_tool.invoke({"query": "reinforcement learning", "top_k": None}) == "hit:reinforcement learning:3"
    assert seen["top_k"] == 3

    rerank_tool = _create_dynamic_reranking_tool(
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "results": {"type": "array"},
            },
            "required": ["query"],
        }
    )
    out = rerank_tool.invoke({"query": "policy gradient", "results": ["doc about policy gradient", "other doc"]})
    assert "BM25 reranked results" in out
    assert "No search results found" in rerank_tool.invoke({"query": "policy gradient"})


