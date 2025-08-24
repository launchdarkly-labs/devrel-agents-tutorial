# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup and Installation:**
```bash
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys
```

**Run the Application:**
```bash
# Backend API
uvicorn api.main:app --reload

# Chat UI (separate terminal)
streamlit run ui/chat_interface.py
```

**Key Environment Variables:**
- `LD_SDK_KEY`: LaunchDarkly Server SDK key
- `ANTHROPIC_API_KEY`: For Claude model access

## Architecture Overview

This is a tutorial project demonstrating LaunchDarkly AI Configs with LangGraph agents. The core concept is runtime control of AI agent behavior through LaunchDarkly's configuration management.

### Request Flow:
1. **FastAPI** (`api/main.py`) receives chat requests
2. **AgentService** (`api/services/agent_service.py`) coordinates the response
3. **ConfigManager** (`policy/config_manager.py`) fetches LaunchDarkly AI Config for the user
4. **LangGraph Agent** (`agents/support_agent.py`) processes the message using static runtime context
5. **Tools** (`tools_impl/`) are conditionally available based on LaunchDarkly configuration

### LaunchDarkly Integration:
- **AI Configs** control model selection, prompts, and tool availability
- **Static Runtime Context** (LangGraph v0.6) passes LaunchDarkly config to agent execution  
- **Variations** tested: none (baseline), docs-only, full-stack (docs + search)

### Key Configuration Points:
- `support-agent-config` flag: Contains model, instructions, allowed_tools, policy limits
- `support-agent-variation` flag: Tracks which variation is active
- Agent receives configuration via `ContextSchema` dataclass

### Simplified Design:
This is streamlined for tutorial purposes - tools return stub responses, no complex error handling, minimal dependencies. The focus is demonstrating LaunchDarkly's runtime control capabilities rather than building a production system.

## LaunchDarkly Configuration

The system expects these LaunchDarkly flags:
- `support-agent-config`: AI Config containing model, instructions, allowed_tools, max_tool_calls, max_cost
- `support-agent-variation`: String flag for tracking active variation

Variations should map to different tool configurations:
- **baseline**: No tools, model-only responses
- **docs-only**: Documentation lookup tool enabled  
- **full-stack**: Both documentation and search tools enabled