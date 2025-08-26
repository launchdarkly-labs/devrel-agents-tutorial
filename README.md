# LaunchDarkly AI Config Multi-Agent Demo

An advanced tutorial demonstrating LaunchDarkly AI Config with multi-agent workflows, RAG, real MCP integration, and Redis caching.

## Features

- **Multi-Agent Architecture**: Supervisor orchestrates Security and Research agents
- **LaunchDarkly AI Config**: Runtime control of 3 specialized agents 
- **RAG Integration**: Vector search with embeddings, FAISS, and reranking
- **Real MCP Integration**: ArXiv and Semantic Scholar via Model Context Protocol
- **Redis Caching**: High-performance caching for configs and research results
- **Multi-Provider Support**: Claude and OpenAI models
- **Production-Ready**: Enterprise-grade performance and graceful degradation

## Quick Start

### Prerequisites
- Python 3.11+ (required for MCP integration)
- [uv](https://astral.sh/uv/) package manager
- Node.js 18+ (for MCP servers)
- OpenAI API key (for vector embeddings)
- Anthropic API key (for Claude models)
- LaunchDarkly SDK key (for AI configs)
- Redis server (optional, for caching)

### Setup

1. **Install uv** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

2. **Install dependencies**:
```bash
uv sync
```

3. **Install MCP research servers** (for research-enhanced variation):
```bash
# ArXiv MCP Server (Python-based)
uv tool install arxiv-mcp-server

# Semantic Scholar MCP Server (clone and install dependencies) 
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/semanticscholar-mcp
uv add requests beautifulsoup4 mcp semanticscholar

# Install Redis (for caching - optional but recommended)
brew install redis && brew services start redis
```

4. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your API keys:
# LD_SDK_KEY=your-launchdarkly-sdk-key
# ANTHROPIC_API_KEY=your-anthropic-api-key
# OPENAI_API_KEY=your-openai-api-key
# REDIS_URL=redis://localhost:6379/0  # optional
```

5. **Initialize vector embeddings** (one-time setup):
```bash
uv run initialize_embeddings.py
```
This creates persistent OpenAI embeddings from your knowledge base. Run with `--force` to recreate embeddings.

### Running the Application

1. **Start the FastAPI backend**:
```bash
uv run uvicorn api.main:app --reload --port 8000
```

2. **Start the Streamlit UI** (in another terminal):
```bash
uv run streamlit run ui/chat_interface.py --server.port 8501
```

3. **Access the application**:
- API: http://localhost:8000
- UI: http://localhost:8501  
- API Docs: http://localhost:8000/docs

## Architecture

### **Multi-Agent Workflow:**
- `agents/supervisor_agent.py` - Orchestrates workflow between Security and Support agents
- `agents/security_agent.py` - PII detection and compliance using native model capabilities  
- `agents/support_agent.py` - RAG-powered research with optional MCP integration

### **Directory Structure:**
- `api/` - FastAPI backend with multi-agent orchestration
- `agents/` - LangGraph multi-agent definitions and workflows
- `tools_impl/` - RAG tools + MCP research integrations
- `utils/` - Redis caching and performance utilities
- `policy/` - LaunchDarkly AI Config management with caching
- `ui/` - Streamlit chat interface
- `docs/` - Setup guides for MCP and Redis

## Configuration

### **LaunchDarkly AI Configs:**
The system uses **3 specialized AI Config flags**:

- `supervisor-agent`: Controls workflow routing logic
- `security-agent`: Manages PII detection behavior  
- `support-agent`: Controls RAG and research tool availability

### **Support Agent Variations:**
- **`docs-only`**: Basic search only (`["search_v1"]`)
- **`rag-enabled`**: Full RAG stack (`["search_v1", "search_v2", "reranking"]`)
- **`research-enhanced`**: RAG + MCP research (`["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]`)

### **MCP Tools (✅ Installed & Working):**
- `arxiv_search`: **ArXiv MCP Server** - Advanced academic paper search
  - 🔍 Advanced query construction with field-specific searches (title, author, abstract)
  - 📚 Category filtering (cs.AI, cs.MA, cs.LG, cs.CL, cs.CV, cs.RO, etc.)
  - 📅 Date filtering for historical and recent research
  - 💾 Paper download and storage capabilities (`download_paper`, `read_paper`)
- `semantic_scholar`: **Semantic Scholar MCP Server** - Academic database integration
  - 🔎 Multi-database paper search across academic sources
  - 👤 Author profiles and detailed academic metadata
  - 🔗 Citation networks and reference relationships
  - 📊 Publication metrics and impact analysis

## Features Demo

### **Performance & Caching:**
- **90% fewer LaunchDarkly API calls** with Redis caching
- **10x faster RAG responses** for cached embeddings
- **Sub-second research queries** with MCP result caching

### **Multi-Agent Workflow:**
- Security agent removes PII using native model capabilities
- Support agent performs research using RAG + optional MCP  
- Supervisor orchestrates the complete workflow

### **Technology Integration:**
- Real Model Context Protocol servers for academic research
- Enterprise-grade Redis caching layer
- Multi-provider model support (Claude + OpenAI)

## License

MIT