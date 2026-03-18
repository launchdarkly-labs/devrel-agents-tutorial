# Multi-Agent Chatbot with LaunchDarkly AI Configs

Demo application for the [Agent Graphs tutorial](https://docs.launchdarkly.com/tutorials/agent-graphs).

## Quick Start

```bash
cp .env.example .env
# Add your LD_SDK_KEY and API keys to .env

uv sync
uv run python initialize_embeddings.py --force
uv run python bootstrap/create_configs.py

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
| `config_manager.py` | **Core LD integration** - fetches AI Configs and Agent Graphs |
| `api/services/agent_service.py` | **Graph orchestration** - traverses Agent Graph, routes between agents |
| `bootstrap/create_configs.py` | Creates AI Configs, tools, segments, and targeting rules in LD |

### Agents
| File | Purpose |
|------|---------|
| `agents/supervisor_agent.py` | Routes requests based on PII likelihood (uses LD AI Config) |
| `agents/security_agent.py` | Detects and redacts PII (uses LD AI Config) |
| `agents/support_agent.py` | Answers questions with tools (uses LD AI Config + tools) |
| `agents/ld_agent_helpers.py` | Shared helpers - model creation, metric tracking |

### Tools
| File | Purpose |
|------|---------|
| `tools_impl/dynamic_tool_factory.py` | Creates tools from LD AI Config definitions |
| `tools_impl/search_v1.py` | Basic keyword search |
| `tools_impl/search_v2.py` | Semantic vector search |
| `tools_impl/reranking.py` | BM25 relevance scoring |
| `tools_impl/mcp_research_tools.py` | MCP tools (arxiv_search, semantic_scholar) |

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
│  • AI Configs (supervisor, security, support)               │
│  • Targeting rules (free/paid, EU/other)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     config_manager.py                        │
│  • get_agent_graph() → fetches graph topology               │
│  • get_config() → fetches AI Config for each agent          │
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
│  • Tracks metrics via config.tracker                        │
└─────────────────────────────────────────────────────────────┘
```

## What You Can Change Without Deploying

| Change | Deploy Required? |
|--------|-----------------|
| Model (gpt-4o → claude-sonnet) | No |
| Prompt/instructions | No |
| Graph edges (routing) | No |
| Targeting rules (user segments) | No |
| Variation rollout percentages | No |
| New agent type | **Yes** (register in `AGENT_REGISTRY`) |
| New tool integration | **Yes** (implement in `tools_impl/`) |
| Routing contract changes | **Yes** (update `_select_next_node()`) |

## Executor Architecture

The `AgentGraphExecutor` is stateless and generic:

- **AGENT_REGISTRY**: Maps node key patterns to factory functions
- **Edge-following**: `while current_node` loop until terminal node
- **Routing**: Matches `routing_decision` to edge `handoff.route`
- **Safety**: Cycle detection, max hop limit (10)

To add a new agent type:
```python
# In agent_service.py
AGENT_REGISTRY["my_agent"] = create_my_agent
```
