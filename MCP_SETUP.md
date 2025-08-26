# MCP Research Tools Setup Guide

This project now includes **real Model Context Protocol (MCP)** integration for academic research capabilities.

## 🚀 Quick Start

The system works out-of-the-box with **fallback tools** when MCP servers aren't available. To unlock full MCP research capabilities:

### 1. Install Node.js (Required for MCP Servers)
```bash
# Install Node.js 18+ if not already installed
brew install node  # macOS
# or download from https://nodejs.org/
```

### 2. Install MCP Research Servers

**ArXiv Research Server:**
```bash
npm install -g @michaellatman/mcp-server-arxiv
```

**Semantic Scholar Server:**
```bash
npm install -g @blazickjp/arxiv-mcp-server
```

**Alternative Research Servers:**
```bash
# Multiple research database access
npm install -g mcp-server-research
```

### 3. Verify Installation
```bash
# Test ArXiv MCP server
npx @michaellatman/mcp-server-arxiv

# Should return server information without errors
```

## 🔧 Configuration

The system automatically detects available MCP servers. When configured properly, you'll see:

- **Real ArXiv API integration** via MCP
- **Semantic Scholar database access** via MCP  
- **Standardized MCP protocol** communication
- **Automatic fallback** when servers unavailable

## 🎯 LaunchDarkly Tool Configuration

**Tool Configurations remain the same:**

### arxiv_search
```json
{
  "properties": {
    "query": {"type": "string", "description": "Search query for arXiv research papers"},
    "max_results": {"type": "integer", "default": 5, "description": "Maximum number of papers"}
  },
  "required": ["query"],
  "type": "object"
}
```

### semantic_scholar  
```json
{
  "properties": {
    "query": {"type": "string", "description": "Academic papers search query"},
    "limit": {"type": "integer", "default": 5, "description": "Number of results"}
  },
  "required": ["query"], 
  "type": "object"
}
```

## 📊 Demo Variations

**`docs-only`**: Internal RAG only
- Tools: `["search_v1"]`

**`rag-enabled`**: Full RAG stack  
- Tools: `["search_v1", "search_v2", "reranking"]`

**`research-enhanced`**: RAG + MCP Research
- Tools: `["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]`

## 🐛 Troubleshooting

### MCP Servers Not Working?
- **Check Node.js version**: `node --version` (needs 18+)
- **Reinstall servers**: `npm uninstall -g @michaellatman/mcp-server-arxiv && npm install -g @michaellatman/mcp-server-arxiv`
- **Check server status**: `npx @michaellatman/mcp-server-arxiv --help`

### Using Fallback Mode?
The system automatically falls back to mock tools when MCP servers aren't available. You'll see messages like:
```
"ArXiv search for 'query' (fallback mode - MCP server not available)"
```

### Enable Debug Logging
```python
import logging
logging.getLogger('tools_impl.mcp_research_tools').setLevel(logging.DEBUG)
```

## 🌟 Benefits of Real MCP Integration

✅ **Real Research Data**: Actual arXiv and academic database access
✅ **Standardized Protocol**: Following official MCP specifications  
✅ **Ecosystem Compatibility**: Works with other MCP-enabled tools
✅ **Community Servers**: Access to growing MCP server ecosystem
✅ **Demo Value**: Shows real-world MCP usage patterns

## 📚 MCP Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/)
- [MCP Servers Repository](https://github.com/modelcontextprotocol/servers) 
- [LangChain MCP Adapters](https://python.langchain.com/docs/integrations/tools/mcp/)
- [Awesome MCP Servers](https://github.com/wong2/awesome-mcp-servers)

Your LaunchDarkly AI Config demo now showcases **real MCP integration** alongside RAG capabilities! 🚀