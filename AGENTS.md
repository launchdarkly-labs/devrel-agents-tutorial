# AGENTS.md

Companion code for the LaunchDarkly tutorial series *Chaos to Clarity: Defensible AI Systems*. A FastAPI service runs a LangGraph supervisor that routes to a security agent (PII detection) and a support agent (RAG over `kb/`), with every model, prompt, and tool selection delivered by LaunchDarkly AI Configs (AgentControl). The tutorials are the product; the code exists so a reader can follow them.

## Setup and commands

- Python 3.11 via `uv`. `uv sync` installs runtime deps; `uv sync --group dev` adds pytest and ruff.
- `cp .env.example .env`. `LD_SDK_KEY` is always required. Choose one model auth path: `AUTH_METHOD=sso` (AWS Bedrock, needs `AWS_PROFILE` + `AWS_REGION`) or `AUTH_METHOD=api-key` (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`). `OPENAI_API_KEY` is also needed to rebuild embeddings.
- API: `uv run uvicorn api.main:app --reload --port 8000`. Smoke check: `curl localhost:8000/health`, then POST `/chat`.
- UI: `uv run streamlit run ui/chat_interface.py --server.port 8501`.
- Embeddings: `uv run python initialize_embeddings.py --force`. `data/vector_store/` is committed so CI never calls OpenAI; rebuild and commit it only when `kb/` changes.
- LaunchDarkly bootstrap: `uv run python bootstrap/create_configs.py` (needs `LD_API_KEY`). Initial setup only. Afterwards LaunchDarkly is the source of truth and `bootstrap/ai_config_manifest.yaml` stays as-is.
- Lint: `uv run ruff check <files you touched>`. The codebase carries a pre-existing ruff baseline (dozens of findings); fix only what your change introduces so PR diffs stay reviewable.

## Verification

There is no unit-test suite in the repo (`tests/` is gitignored). Correctness is verified end to end:

1. API starts clean with your `.env` and `/health` returns 200.
2. A `/chat` request routes through supervisor → security/support and the response names the served config variation.
3. CI (`.github/workflows/ai-config-validation.yml`) runs the `ld-aic-cicd` validator and LLM judge against the live LaunchDarkly project on every PR. It needs org secrets, so expect it to run on the PR, not locally.

Done means steps 1 and 2 pass locally for the tutorial part you changed.

## Names are contracts

Tutorial readers create these by hand in the LaunchDarkly UI, so the same strings appear in the tutorials, the manifest, and the code. Renaming one means renaming all three.

- Project `multi-agent-chatbot`
- AI Configs `supervisor-agent`, `security-agent`, `support-agent`
- Tools `search_v2`, `reranking`
- Variations `supervisor-basic`, `pii-detector`, `rag-search-enhanced`

## Tutorials are published MDX

`README.md`, `tutorial_2.md`, and `tutorial_3.md` are synced verbatim into the LaunchDarkly docs site. Keep the frontmatter, `<Callout>`, `<Frame>`, and `<Note>` components, and the `screenshots/` paths intact. Command examples in the tutorials must match what the code actually accepts; when you change a CLI flag or env var, update the tutorial in the same commit.

## Branches

`main` is Part 1. `tutorial-2` and `tutorial-3` hold the code state for Parts 2 and 3; `tutorial/agent-graphs` is the newer Agent Graphs rewrite. Work on the branch that matches the tutorial part you are changing; the parts diverge deliberately.

## Bedrock

Model IDs in LaunchDarkly should be inference-profile IDs with a region prefix (`us.anthropic.claude-...`). `utils/bedrock_helpers.py` auto-prefixes bare IDs using `BEDROCK_INFERENCE_REGION`, then `AWS_REGION`, then `us`; keep that behaviour when touching model resolution. `AccessDeniedException` usually means the account in `AWS_PROFILE` differs from the one named in the error message.
