# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup and Installation:**
```bash
uv sync
cp .env.example .env  # Edit with your API keys

# For MCP research tools (research-enhanced variation)
uv tool install arxiv-mcp-server
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/semanticscholar-mcp
uv add requests beautifulsoup4 mcp semanticscholar

# For Redis caching (optional but recommended)
brew install redis && brew services start redis
```

**Run the Application:**
```bash
# Backend API
uv run uvicorn api.main:app --reload

# Chat UI (separate terminal)
uv run streamlit run ui/chat_interface.py
```

**Key Environment Variables:**
- `LD_SDK_KEY`: LaunchDarkly Server SDK key
- `ANTHROPIC_API_KEY`: For Claude model access
- `OPENAI_API_KEY`: For OpenAI model access
- `REDIS_URL`: Redis connection string (optional, defaults to localhost)

## Architecture Overview

This is an advanced tutorial project demonstrating LaunchDarkly AI Configs with multi-agent LangGraph workflows, real MCP integration, and Redis caching.

### Multi-Agent Architecture:
1. **FastAPI** (`api/main.py`) receives chat requests
2. **AgentService** (`api/services/agent_service.py`) orchestrates the multi-agent workflow
3. **ConfigManager** (`policy/config_manager.py`) fetches LaunchDarkly AI Configs with Redis caching
4. **Supervisor Agent** (`agents/supervisor_agent.py`) routes between specialized agents
5. **Security Agent** (`agents/security_agent.py`) handles PII detection using native model capabilities
6. **Support Agent** (`agents/support_agent.py`) performs research using RAG + MCP tools

### LaunchDarkly Integration:
- **3 AI Configs** control different agent behaviors: supervisor-agent, support-agent, security-agent
- **Runtime Control** over tool availability, model selection, and agent instructions
- **Redis Caching** reduces LaunchDarkly API calls by 90%
- **Variations** tested: docs-only, rag-enabled, research-enhanced (with MCP)

### Technology Stack:
- **RAG**: Vector search with OpenAI embeddings, FAISS, and semantic reranking
- **MCP**: Real Model Context Protocol integration with ArXiv and Semantic Scholar
- **Redis**: High-performance caching for configs, embeddings, and MCP responses
- **Multi-Provider**: Supports both Anthropic Claude and OpenAI GPT models

### Production-Ready Features:
- Multi-agent workflows with state management
- Real academic research capabilities via MCP servers
- Enterprise-grade caching and performance optimization
- Graceful degradation when optional services unavailable

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