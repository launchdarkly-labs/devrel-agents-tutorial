"""Shared setup for the unit tests: no network, no real keys, run from the repo root."""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Set before the app modules import and load .env, which never overrides existing values
os.environ["LD_SDK_KEY"] = "sdk-test-key"
os.environ["LD_API_KEY"] = "api-test-key"
os.environ["AUTH_METHOD"] = "api-key"
os.environ["CI_SAFE_MODE"] = ""


@pytest.fixture(autouse=True)
def run_from_repo_root(monkeypatch):
    """The config manager reads .ai_config_defaults.json from the working directory."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture(autouse=True)
def no_rate_limit_sleep(monkeypatch):
    """The agents pause between model calls; the fakes don't need that."""
    import agents.ld_agent_helpers as helpers
    import agents.security_agent as security
    import agents.supervisor_agent as supervisor

    for module in (helpers, security, supervisor):
        monkeypatch.setattr(module, "_rate_limit_llm_call", lambda: None)
