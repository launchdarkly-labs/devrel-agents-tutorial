# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup and Installation:**
```bash
uv sync
cp .env.example .env  # Edit with your API keys

# For MCP research tools (research-enhanced variation)
uv tool install arxiv-mcp-server
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git
uv add requests beautifulsoup4 mcp semanticscholar

```

**Run the Application:**
```bash
# Backend API
uv run uvicorn api.main:app --reload --port 8001

# Chat UI (separate terminal)
uv run streamlit run ui/chat_interface.py

# Traffic Generator (for experiments and blog posts)
python tools/traffic_generator.py --queries 50 --delay 2
```

**Traffic Simulation:**
```bash
# Generate realistic LaunchDarkly experiment data
python tools/traffic_generator.py --queries 100 --delay 1

# Quick test with verbose output  
python tools/traffic_generator.py --queries 10 --delay 2 --verbose

# Batch generation for blog post metrics
python tools/traffic_generator.py --queries 500 --delay 0.5
```

**Key Environment Variables:**
- `LD_SDK_KEY`: LaunchDarkly Server SDK key
- `ANTHROPIC_API_KEY`: For Claude model access
- `OPENAI_API_KEY`: For OpenAI model access

## Architecture Overview

This is an advanced tutorial project demonstrating LaunchDarkly AI Configs with multi-agent LangGraph workflows and real MCP integration.

### Multi-Agent Architecture:
1. **FastAPI** (`api/main.py`) receives chat requests
2. **AgentService** (`api/services/agent_service.py`) orchestrates the multi-agent workflow
3. **ConfigManager** (`policy/config_manager.py`) fetches LaunchDarkly AI Configs
4. **Supervisor Agent** (`agents/supervisor_agent.py`) routes between specialized agents
5. **Security Agent** (`agents/security_agent.py`) handles PII detection using native model capabilities
6. **Support Agent** (`agents/support_agent.py`) performs research using RAG + MCP tools

### LaunchDarkly Integration:
- **3 AI Configs** control different agent behaviors: supervisor-agent, support-agent, security-agent
- **Runtime Control** over tool availability, model selection, and agent instructions
- **Variations** tested: docs-only, rag-enabled, research-enhanced (with MCP)

### Technology Stack:
- **RAG**: Vector search with OpenAI embeddings, FAISS, and semantic reranking
- **MCP**: Real Model Context Protocol integration with ArXiv and Semantic Scholar
- **Multi-Provider**: Supports both Anthropic Claude and OpenAI GPT models

### Production-Ready Features:
- Multi-agent workflows with state management
- Real academic research capabilities via MCP servers

## LaunchDarkly Configuration

The system uses **3 AI Config flags** for multi-agent control:

### **Required AI Configs:**
- `supervisor-agent`: Orchestrates workflow between agents
- `support-agent`: Controls RAG + MCP research tools  
- `security-agent`: Handles PII detection and compliance

### **Tool Variations:**

**Support Agent Variations:**
- **`docs-only`**: `["search_v1"]` - Basic search only
- **`rag-enabled`**: `["search_v1", "search_v2", "reranking"]` - Full RAG stack
- **`research-enhanced`**: `["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]` - RAG + MCP research

**Security Agent Variations:**
- **`baseline`**: No tools, native model PII detection
- **`enhanced`**: Native model with enhanced instructions

**MCP Tools (✅ Installed & Working):**
- `arxiv_search`: ArXiv MCP Server - Advanced academic paper search with filtering and downloads
- `semantic_scholar`: Semantic Scholar MCP Server - Academic database integration with citations

### **MCP Server Status:**
Both MCP servers are **successfully installed and working**:
- **ArXiv Server**: `arxiv-mcp-server` (Python-based, installed via uv)
- **Semantic Scholar Server**: `semanticscholar-MCP-Server` (Python-based, cloned from GitHub)

The multi-agent system automatically initializes MCP tools in background threads to avoid async event loop conflicts.

## Traffic Simulation

The project includes a **dead-simple traffic generator** for creating realistic LaunchDarkly experiment data:

### **Key Files:**
- `tools/traffic_generator.py`: Main script (high school student friendly)
- `data/fake_users.json`: Geographic users (US, EU, Asia) with different plans
- `data/sample_queries.json`: AI/ML questions with expected responses
- `data/feedback_rules.json`: Configurable satisfaction simulation rules

### **How It Works:**
1. **Real User Simulation**: Fake users with geographic/plan attributes
2. **Real API Calls**: Sends actual requests to `/chat` endpoint
3. **Real AI Responses**: Multi-agent system responds naturally with real MCP tools
4. **Simulated Feedback**: Smart rules determine thumbs up/down based on response quality
5. **Real LaunchDarkly Metrics**: Authentic experiment data flows to dashboard

### **Geographic Targeting:**
- **EU Users**: Get Claude (privacy compliance) 
- **Enterprise Users**: Get expensive MCP research tools
- **Free Users**: Get basic tools only
- **US Users**: Mixed variations for A/B testing

This generates compelling, authentic metrics for blog posts and tutorials demonstrating LaunchDarkly AI Config optimization.