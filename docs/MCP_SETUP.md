# MCP Research Tools Setup

This document describes the Model Context Protocol (MCP) integration for academic research capabilities in the LaunchDarkly AI Config demo.

## ✅ Current Status: INSTALLED & WORKING

Both MCP research servers are successfully installed and operational:
- **ArXiv MCP Server**: Advanced academic paper search
- **Semantic Scholar MCP Server**: Academic database integration

## MCP Servers Overview

### 1. ArXiv MCP Server
**Repository**: `blazickjp/arxiv-mcp-server`  
**Installation**: `uv tool install arxiv-mcp-server`  
**Path**: `/Users/ld_scarlett/.local/bin/arxiv-mcp-server`

**Available Tools:**
- `search_papers`: Advanced ArXiv search with query optimization
- `download_paper`: Download papers and create resources
- `list_papers`: List all stored papers  
- `read_paper`: Read full paper content in markdown

**Features:**
- 🔍 Advanced query construction (field-specific, quoted phrases)
- 📚 Category filtering (cs.AI, cs.MA, cs.LG, cs.CL, etc.)
- 📅 Date filtering for historical/recent research
- 💾 Paper storage and retrieval system

### 2. Semantic Scholar MCP Server  
**Repository**: `JackKuo666/semanticscholar-MCP-Server`  
**Installation**: Cloned to `/tmp/semanticscholar-mcp/`  
**Path**: `/tmp/semantic_scholar_server.py`

**Available Tools:**
- `search_semantic_scholar`: Multi-database academic search
- `get_semantic_scholar_paper_details`: Detailed paper metadata
- `get_semantic_scholar_author_details`: Author profiles
- `get_semantic_scholar_citations_and_references`: Citation networks

**Features:**
- 🔎 Cross-database academic paper search
- 👤 Author profile and academic metadata
- 🔗 Citation and reference relationship mapping
- 📊 Publication metrics and impact analysis

## Installation Commands

### Prerequisites
```bash
# Ensure Python 3.11+ for MCP compatibility
python --version

# Install dependencies
uv sync
```

### Install MCP Servers
```bash
# ArXiv MCP Server (Python-based)
uv tool install arxiv-mcp-server

# Semantic Scholar MCP Server 
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/semanticscholar-mcp
cp -r /tmp/semanticscholar-mcp/* /tmp/
uv add requests beautifulsoup4 mcp semanticscholar
```

### Verify Installation
```bash
# Check ArXiv server
/Users/ld_scarlett/.local/bin/arxiv-mcp-server --help

# Check Semantic Scholar dependencies
uv run python -c "import semanticscholar; print('✅ Semantic Scholar package installed')"
uv run python -c "import mcp; print('✅ MCP package installed')"
```

## Configuration

The MCP servers are automatically configured in `/tools_impl/mcp_research_tools.py`:

```python
server_configs = {
    "arxiv": {
        "command": "/Users/ld_scarlett/.local/bin/arxiv-mcp-server",
        "args": ["--storage-path", "/tmp/arxiv-papers"]
    },
    "semanticscholar": {
        "command": "python", 
        "args": ["/tmp/semantic_scholar_server.py"]
    }
}
```

## Tool Mapping

The MCP tools are mapped to LaunchDarkly configuration names:

- `arxiv_search` ➜ `search_papers` (ArXiv MCP Server)
- `semantic_scholar` ➜ `search_semantic_scholar` (Semantic Scholar MCP Server)

## LaunchDarkly Configuration

To enable MCP research tools, add them to the `support-agent` AI Config:

```json
{
  "model": {
    "name": "claude-3-5-sonnet-20241022",
    "parameters": {
      "tools": [
        {"name": "search_v1"},
        {"name": "search_v2"}, 
        {"name": "reranking"},
        {"name": "arxiv_search"},
        {"name": "semantic_scholar"}
      ]
    },
    "custom": {
      "max_tool_calls": 8,
      "max_cost": 1.0,
      "workflow_type": "sequential"
    }
  },
  "instructions": "You are a research assistant with access to academic databases..."
}
```

## Usage Examples

### ArXiv Search
```python
# Query: "reinforcement learning multi-agent systems"
# Categories: ["cs.AI", "cs.MA"] 
# Date filter: Recent papers (2020+)
```

### Semantic Scholar Search
```python
# Query: "transformer architecture attention mechanisms"
# Returns: Papers, authors, citations, references
```

## Troubleshooting

### Common Issues:

**1. MCP Import Errors**
```bash
# Fix: Ensure all dependencies installed
uv add requests beautifulsoup4 mcp semanticscholar
```

**2. Async Event Loop Conflicts**
```
Fixed: Using ThreadPoolExecutor for background MCP initialization
```

**3. Missing MCP Tools**
```
Check: "DEBUG: Loaded X tools from Y MCP server" in logs
```

### Verification Commands:
```bash
# Test API with MCP tools
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Search ArXiv for recent AI papers"}'

# Check server logs for MCP initialization
# Look for: "DEBUG: Loaded real MCP tools: ['search_papers', 'search_semantic_scholar']"
```

## Performance Notes

- MCP initialization runs in background threads to avoid blocking the main event loop
- Tools are cached after first load for better performance
- Redis caching available for MCP results (optional)
- Graceful degradation when MCP servers unavailable

## Security Considerations

- MCP servers run in isolated processes
- No external network access beyond academic APIs
- Paper downloads stored in `/tmp/arxiv-papers` (temporary)
- All academic content is publicly available research

---

## System Integration Status: ✅ COMPLETE

The MCP research integration is **fully operational** with:
- ✅ Both servers installed and working
- ✅ All 8 research tools available (4 ArXiv + 4 Semantic Scholar) 
- ✅ Proper async handling and background initialization
- ✅ LaunchDarkly AI Config integration
- ✅ Multi-agent workflow compatibility

Ready for production use with the `research-enhanced` variation! 🚀