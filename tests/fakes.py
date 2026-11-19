"""Small stand-ins for the model, the agents, and the config manager, so tests never call an API."""
import inspect
from langchain_core.messages import AIMessage

from config_manager import ServedConfig


def served(key, model="claude-haiku-5-5", custom=None, tools=None, variation_key=None):
    """A config as LaunchDarkly would serve it, or a local fallback when variation_key is None."""
    tool_list = tools or []
    config = {
        "model": {"name": model, "custom": custom or {}, "parameters": {"tools": tool_list}},
        "provider": {"name": "Anthropic"},
        "instructions": f"You are the {key}.",
        "tools": {
            t["name"]: {**t, "type": "function"}
            for t in tool_list
            if isinstance(t, dict) and "name" in t
        },
    }
    if variation_key is None:
        return ServedConfig(key=key, config=config, from_fallback=True)
    return ServedConfig(
        key=key,
        config=config,
        meta={"variationKey": variation_key, "version": 1, "modelKey": f"Anthropic.{model}", "modelVersion": 1},
    )


class FakeConfigManager:
    """Serves fixed configs and runs model calls without sending events."""

    def __init__(self, configs):
        self.configs = configs

    async def get_config(self, user_id, config_key, user_context=None):
        return self.configs[config_key]

    def build_context(self, user_id, user_context=None):
        return {"kind": "user", "key": user_id, **(user_context or {})}

    async def track(self, served_config, context, call, user_input=None, tool_handlers=None):
        takes_args = len(inspect.signature(call).parameters) > 0
        out = await (call(tool_handlers or {}, {"ldContext": context}) if takes_args else call())
        return out[0]


class FakeStructuredModel:
    """Returns one structured result, like with_structured_output(..., include_raw=True)."""

    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error

    def with_structured_output(self, schema, include_raw=False):
        return self

    async def ainvoke(self, messages):
        if self.error:
            raise self.error
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        return {"parsed": self.parsed, "raw": AIMessage(content="", usage_metadata=usage)}


class RecordingSupportAgent:
    """Records exactly what the support agent receives."""

    def __init__(self):
        self.received = None

    async def ainvoke(self, request_data):
        self.received = request_data
        return {"response": "Here is what I found.", "tool_calls": [], "tool_details": []}


class FixedSecurityAgent:
    """Returns a fixed PII result instead of calling a model."""

    def __init__(self, redacted, detected=True):
        self.result = {"detected": detected, "types": ["email"] if detected else [], "redacted": redacted,
                       "response": "PII Analysis: done"}

    async def ainvoke(self, request_data):
        return self.result
