# MCP Research Integration Guide

**Status**: ✅ **FULLY OPERATIONAL** - ArXiv and Semantic Scholar MCP servers working

This document covers the complete Model Context Protocol (MCP) integration for academic research capabilities in the LaunchDarkly AI Config Multi-Agent Demo.

---

## 🚀 Quick Setup

### Prerequisites
```bash
# Ensure Python 3.11+ and uv
python --version
uv --version

# Install dependencies
uv sync
cp .env.example .env  # Add your API keys (LD_SDK_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY)
```

### Install MCP Servers
```bash
# 1. ArXiv MCP Server (Python-based) - WORKING ✅
uv tool install arxiv-mcp-server

# 2. Semantic Scholar MCP Server - OPTIONAL ⚠️
# Clone to /tmp/arxiv-mcp/ if you want Semantic Scholar integration:
# git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/arxiv-mcp/semanticscholar-MCP-Server
# uv add requests beautifulsoup4 mcp semanticscholar

# 3. Initialize vector embeddings (one-time)
uv run initialize_embeddings.py
```

### Verify Installation
```bash
# Check ArXiv server - WORKING ✅
arxiv-mcp-server --help

# Check Semantic Scholar dependencies (if installed)
# uv run python -c "import semanticscholar; print('✅ Semantic Scholar ready')"
# uv run python -c "import mcp; print('✅ MCP package ready')"
```

### Run the System
```bash
# Backend API
uv run uvicorn api.main:app --reload --port 8001

# Frontend UI (optional)
uv run streamlit run ui/chat_interface.py --server.port 8501
```

---

## 🔧 MCP Server Details

### ArXiv MCP Server
- **Repository**: `blazickjp/arxiv-mcp-server`
- **Installation**: `uv tool install arxiv-mcp-server`


**Available Tools:**
- `search_papers`: Advanced ArXiv search with query optimization
- `download_paper`: Download papers and create resources
- `list_papers`: List all stored papers
- `read_paper`: Read full paper content in markdown

**Features:**
- 🔍 Advanced query construction (field-specific, quoted phrases)
- 📚 Category filtering (cs.AI, cs.MA, cs.LG, cs.CL, etc.)
- 📅 Date filtering for recent research
- 💾 Paper storage and retrieval

### Semantic Scholar MCP Server  
- **Repository**: `JackKuo666/semanticscholar-MCP-Server`
- **Installation**: Clone and setup in temporary directory

**Available Tools:**
- `search_semantic_scholar`: Multi-database academic search
- `get_semantic_scholar_paper_details`: Detailed paper metadata
- `get_semantic_scholar_author_details`: Author profiles  
- `get_semantic_scholar_citations_and_references`: Citation networks

**Features:**
- 🔎 Cross-database academic paper search
- 👤 Author profiles and academic metadata
- 🔗 Citation and reference relationship mapping
- 📊 Publication metrics and impact analysis

---

## 🎯 LaunchDarkly Integration

### Tool Name Translation
LaunchDarkly tool names get translated to actual MCP tool names:

**LaunchDarkly Config** → **Actual Tool Called** → **API Response Shows**
- `arxiv_search` → `search_papers` → `"search_papers"`
- `semantic_scholar` → `search_semantic_scholar` → `"search_semantic_scholar"` 
- `search_v2` → `search_vector` → `"search_vector"`
- `reranking` → `reranking` → `"reranking"`

### Tool Variations

**docs-only**: `["search_v2"]`
- Internal RAG only, fast responses

**rag-enabled**: `["search_v2", "reranking"]`  
- Full RAG stack with BM25 reranking algorithm

**research-enhanced**: `["search_v2", "reranking", "arxiv_search", "semantic_scholar"]`
- Complete research capabilities via MCP servers
- **Requires MCP servers installed**

### LaunchDarkly AI Config Example
```json
{
  "model": {
    "name": "claude-3-5-sonnet-20241022",
    "parameters": {
      "tools": [
        {
          "name": "search_v2",
          "description": "📚 INTERNAL: Advanced vector search through knowledge base",
          "type": "function"
        },
        {
          "name": "reranking", 
          "description": "📊 INTERNAL: BM25 algorithm for result reranking",
          "type": "function"
        },
        {
          "name": "arxiv_search",
          "description": "🔬 MCP: ArXiv research papers via external MCP server",
          "type": "function"
        },
        {
          "name": "semantic_scholar",
          "description": "🔬 MCP: Academic papers via Semantic Scholar MCP server", 
          "type": "function"
        }
      ]
    },
    "custom": {
      "max_tool_calls": 8,
      "max_cost": 1.0
    }
  },
  "instructions": "You are a research assistant with access to internal knowledge and external academic databases via MCP..."
}
```

---

## 🧪 Testing

### Verify MCP Tools Working
```bash
# Test with research query
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test", 
    "message": "Find recent papers on reinforcement learning and transformers"
  }'

# Look for in response:
# "tool_calls": ["search_papers", "search_semantic_scholar", "search_vector"]
```

**API Response Example:**
```json
{
  "id": "uuid-here",
  "response": "Generated response with research results...",
  "tool_calls": ["search_papers", "search_semantic_scholar", "search_vector", "search_papers"],
  "variation_key": "pii-and-compliance",
  "model": "claude-3-7-sonnet-latest",
  "agent_configurations": [
    {
      "agent_name": "supervisor-agent",
      "variation_key": "pii-and-compliance", 
      "model": "claude-3-7-sonnet-latest",
      "tools": []
    },
    {
      "agent_name": "security-agent",
      "variation_key": "pii-and-compliance",
      "model": "claude-3-7-sonnet-latest", 
      "tools": []
    },
    {
      "agent_name": "support-agent",
      "variation_key": "full-stack-claude",
      "model": "claude-3-7-sonnet-latest",
      "tools": ["search_papers", "search_semantic_scholar", "search_vector", "search_papers"]
    }
  ]
}
```

**Key Points**:
- The API response shows actual MCP tool names, not LaunchDarkly config names
- Tool calls may include duplicates when tools are called multiple times  
- All three agents show their configurations (supervisor and security have empty tools arrays)

---

## 📊 System Architecture

### Multi-Agent Workflow
1. **Supervisor Agent** - Orchestrates the workflow
2. **Security Agent** - PII detection using native model capabilities  
3. **Support Agent** - Research and retrieval using RAG + MCP tools

### Performance Features
- **Vector Embeddings**: Persistent FAISS storage (188 document chunks)
- **MCP Caching**: Tools cached after first load
- **Async Handling**: Background MCP initialization, no blocking

---

## 🛠️ Troubleshooting

### MCP Tools Not Loading?
**Check server logs for:**
```
DEBUG: ArXiv MCP tool requested but search_papers not available
DEBUG: Semantic Scholar MCP tool requested but search_semantic_scholar not available
```

**Solutions:**
1. Verify MCP servers installed: `which arxiv-mcp-server`
2. Check dependencies: `uv run python -c "import mcp, semanticscholar"`
3. Restart the application to reload MCP tools

### Common Issues

**Import Errors:**
```bash
# Fix: Ensure all dependencies installed
uv add requests beautifulsoup4 mcp semanticscholar
```

**Missing Research Results:**
- Verify LaunchDarkly configuration includes `arxiv_search` and `semantic_scholar`

---

## 🎯 Production Deployment

### Required Environment Variables
```bash
LD_SDK_KEY=your_launchdarkly_key
ANTHROPIC_API_KEY=your_anthropic_key  
OPENAI_API_KEY=your_openai_key
```

### Performance Expectations
- **Basic queries**: ~5-10 seconds
- **RAG queries**: ~10-20 seconds
- **MCP research**: ~20-30 seconds (first time), faster with caching

---

## 📚 Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/)
- [ArXiv MCP Server](https://github.com/blazickjp/arxiv-mcp-server)
- [Semantic Scholar MCP Server](https://github.com/JackKuo666/semanticscholar-MCP-Server)
- [LangChain MCP Adapters](https://python.langchain.com/docs/integrations/tools/mcp/)

---

## ✅ System Ready

**The LaunchDarkly AI Config Multi-Agent Demo is now fully operational with:**
- ✅ Real academic research via MCP protocol
- ✅ Multi-agent workflow orchestration  
- ✅ Runtime configuration via LaunchDarkly AI Config
- ✅ Production-ready performance optimizations

**Ready for LaunchDarkly AI Config demonstrations! 🚀**
