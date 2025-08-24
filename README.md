# Agents You Can Defend: Support Agent Tool Efficiency Platform

A comprehensive AI agent evaluation platform demonstrating LaunchDarkly AI Configs for measuring and optimizing tool efficiency in support agents.

## Features

- **LaunchDarkly AI Configs**: Runtime control of models, prompts, and tool configurations
- **Tool Efficiency Measurement**: Compare different tool combinations (none, docs only, full stack)  
- **LangGraph Integration**: Static runtime context for agent configuration
- **Multi-arm Testing**: Experiment with different agent variations

## Quick Start

### Prerequisites
- Python 3.9+
- [uv](https://astral.sh/uv/) package manager

### Setup

1. **Install uv** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

2. **Create virtual environment and install dependencies**:
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

3. **Set up LaunchDarkly** (optional for demo):
```bash
export LAUNCHDARKLY_SDK_KEY="your-sdk-key-here"
```

### Running the Application

1. **Start the FastAPI backend**:
```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

2. **Start the Streamlit UI** (in another terminal):
```bash
source .venv/bin/activate
streamlit run ui/chat_interface.py --server.port 8501
```

3. **Access the application**:
- API: http://localhost:8000
- UI: http://localhost:8501  
- API Docs: http://localhost:8000/docs

## Architecture

- `api/` - FastAPI backend with LangGraph agent orchestration
- `agents/` - LangGraph agent definitions and workflows
- `tools_impl/` - LangChain tool implementations (docs, search, redaction)
- `policy/` - LaunchDarkly policy enforcement and configuration management
- `ld/` - LaunchDarkly AI Config setup and utilities
- `ui/` - Streamlit chat interface
- `tools/` - Evaluation scripts and test utilities

## Configuration

The system uses LaunchDarkly AI Configs for runtime control:

- **Variation A**: No tools (baseline)
- **Variation B**: Documentation lookup only
- **Variation C**: Full tool stack (lookup + search + redaction)

## Metrics

Key metrics tracked in LaunchDarkly:
- Task success rate
- Tool efficiency (useful vs. extraneous calls)
- Cost per request
- P95 latency
- User satisfaction

## License

MIT