# Multi-Agent Chatbot with LaunchDarkly Agent Management

Demo application for the [Agent Graphs tutorial](https://docs.launchdarkly.com/tutorials/agent-graphs).

## Prerequisites

- **Python 3.12+** with [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- **LaunchDarkly account** ([sign up for free](https://app.launchdarkly.com/signup)) and a **Writer API access token** (`LD_API_KEY`, created under **Settings → Authorization → Create token**)
- **OpenAI API key** ([platform.openai.com/api-keys](https://platform.openai.com/api-keys))
- **Anthropic API key** ([console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys))
- **Mistral API key** ([console.mistral.ai](https://console.mistral.ai/), optional, used for EU security routing)

## Quick Start

```bash
cp .env.example .env
# 1. Add LD_API_KEY, OPENAI_API_KEY, and ANTHROPIC_API_KEY (plus optional MISTRAL_API_KEY) to .env

uv sync
uv run python initialize_embeddings.py --force
(cd bootstrap && uv run python create_configs.py)
# 2. Copy the Production SDK key printed by create_configs.py into LD_SDK_KEY in .env

# Terminal 1
uv run uvicorn api.main:app --reload --port 8000

# Terminal 2
uv run streamlit run ui/chat_interface.py --server.port 8501
```

Open http://localhost:8501

---

## File Structure

### Entry Points
| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI server - `/chat` endpoint |
| `ui/chat_interface.py` | Streamlit chat UI |

### LaunchDarkly Integration
| File | Purpose |
|------|---------|
| `config_manager.py` | **Core LD integration** - fetches AI configs and agent graphs |
| `api/services/agent_service.py` | **Graph orchestration** - traverses Agent Graph, routes between agents |
| `bootstrap/create_configs.py` | Creates AI configs, tools, segments, and targeting rules in LD |

### Agents
| File | Purpose |
|------|---------|
| `agents/generic_agent.py` | Runs any graph node (supervisor, security, support) from its AI config and tools |
| `agents/ld_agent_helpers.py` | Shared helpers - model creation, tool call limits |

### Tools
| File | Purpose |
|------|---------|
| `tools_impl/dynamic_tool_factory.py` | Creates tools from AI config definitions |
| `tools_impl/search_v1.py` | Basic keyword search |
| `tools_impl/search_v2.py` | Semantic vector search |
| `tools_impl/reranking.py` | BM25 relevance scoring |

### Data & Utils
| File | Purpose |
|------|---------|
| `data/vector_store.py` | FAISS vector store for search |
| `data/enterprise_kb.py` | Knowledge base loader |
| `initialize_embeddings.py` | Builds vector index from PDFs |
| `utils/logger.py` | Logging helpers |

---

## How LaunchDarkly Integrates

```
┌─────────────────────────────────────────────────────────────┐
│                    LaunchDarkly Dashboard                    │
│  • Agent Graph (chatbot-flow)                               │
│  • AI configs (supervisor, security, support)               │
│  • Targeting rules (free/paid, EU/other)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     config_manager.py                        │
│  • get_agent_graph() → fetches graph topology               │
│  • track_feedback() → sends thumbs up/down events           │
│  • Handles targeting based on user context                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 api/services/agent_service.py                │
│  • Traverses graph by following edges (while loop)          │
│  • Routes based on edge handoff metadata                    │
│  • Tracks metrics (duration, tokens, tool calls)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      agents/*.py                             │
│  • Each agent receives config from LD                       │
│  • Uses config.instructions, config.model                   │
│  • Executor sends metrics through the graph tracker         │
└─────────────────────────────────────────────────────────────┘
```

## What You Can Change Without Deploying

| Change | Deploy Required? |
|--------|-----------------|
| Model (gpt-6-luna → claude-sonnet-5-5) | No |
| Prompt/instructions | No |
| Graph edges (routing) | No |
| Targeting rules (user segments) | No |
| Variation rollout percentages | No |
| New agent node (using existing tools) | No |
| New tool integration | **Yes** (implement in `tools_impl/`) |
| Routing contract changes | **Yes** (update `_select_next_node()`) |

## Executor Architecture

The `AgentGraphExecutor` is stateless and generic:

- **Generic node runner (`create_generic_agent`)**: Builds each node at runtime from its LaunchDarkly AI config, instructions, and tools
- **Edge-following**: `while current_node` loop until terminal node
- **Routing**: Matches `routing_decision` to edge `handoff.route`
- **Safety**: Cycle detection, max hop limit (10)

To add a new agent node, create its AI config in LaunchDarkly and connect it with an edge in the `chatbot-flow` agent graph—`AgentGraphExecutor` executes it automatically through `create_generic_agent` without code changes unless it needs a new tool in `tools_impl/`.
