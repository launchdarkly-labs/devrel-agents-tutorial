"""With AUTH_METHOD=sso, model names from LaunchDarkly become Bedrock inference profile IDs."""
import pytest

from utils.bedrock_helpers import ensure_bedrock_inference_profile
from utils.cost_calculator import calculate_cost


@pytest.fixture(autouse=True)
def no_region_override(monkeypatch):
    monkeypatch.delenv("BEDROCK_INFERENCE_REGION", raising=False)


@pytest.mark.parametrize("model_id, expected", [
    ("claude-haiku-5-5", "us.anthropic.claude-haiku-5-5"),
    ("anthropic.claude-sonnet-5-5", "us.anthropic.claude-sonnet-5-5"),
    ("us.anthropic.claude-opus-5-5", "us.anthropic.claude-opus-5-5"),
    ("global.anthropic.claude-haiku-5-5", "global.anthropic.claude-haiku-5-5"),
    ("us-gov.anthropic.claude-haiku-5-5", "us-gov.anthropic.claude-haiku-5-5"),
])
def test_model_ids_become_inference_profiles(model_id, expected):
    assert ensure_bedrock_inference_profile(model_id, "us-east-1") == expected


def test_inference_region_override(monkeypatch):
    monkeypatch.setenv("BEDROCK_INFERENCE_REGION", "eu")
    assert ensure_bedrock_inference_profile("claude-haiku-5-5", "us-east-1") == "eu.anthropic.claude-haiku-5-5"


def test_bedrock_ids_are_priced_by_claude_tier():
    assert calculate_cost("us.anthropic.claude-haiku-5-5", 1_000_000, 0) == calculate_cost("claude-haiku-5-5", 1_000_000, 0)
