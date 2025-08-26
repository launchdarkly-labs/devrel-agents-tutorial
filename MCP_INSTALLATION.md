# MCP Installation Guide - Required for Research Tools

Your LaunchDarkly AI Config demo now uses **real MCP integration only** - no mock results. You **must install MCP servers** to enable research capabilities.

## ⚠️ **Important: MCP Required**

Without MCP servers installed:
- ✅ RAG tools work (search_v1, search_v2, reranking) 
- ❌ Research tools don't work (arxiv_search, semantic_scholar)
- 🔧 System shows installation instructions in logs

## 🚀 **Quick MCP Setup**

### **1. Install Node.js (Required)**
```bash
# Check if installed
node --version
# Need v18+ 

# Install if needed:
# macOS
brew install node

# Ubuntu/Linux
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

# Windows
# Download from https://nodejs.org/
```

### **2. Install MCP Research Servers**
```bash
# Primary ArXiv server (recommended)
npm install -g @michaellatman/mcp-server-arxiv

# Alternative research servers
npm install -g @blazickjp/arxiv-mcp-server
npm install -g mcp-server-semantic-scholar
```

### **3. Verify Installation**
```bash
# Test ArXiv MCP server
npx @michaellatman/mcp-server-arxiv --help

# Should show server info without errors
```

## ✅ **Verification**

### **Debug Output - Success:**
```
DEBUG: Loaded real MCP tools: ['arxiv_search']
DEBUG: Added real ArXiv MCP tool
```

### **Debug Output - MCP Missing:**
```
DEBUG: No MCP tools available - install MCP servers for research capabilities
DEBUG: ArXiv MCP tool requested but not available - install: npm install -g @michaellatman/mcp-server-arxiv
```

## 🎯 **LaunchDarkly Variation Strategy**

### **`docs-only` - No MCP Required**
```json
"tools": ["search_v1"]
```
- Works without MCP
- Basic document search only

### **`rag-enabled` - No MCP Required**
```json
"tools": ["search_v1", "search_v2", "reranking"]
```
- Full RAG stack
- Vector search and reranking
- No external research

### **`research-enhanced` - MCP Required**
```json
"tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]
```
- Full RAG + real research tools
- **Requires MCP servers installed**
- Real academic paper search

## 🔧 **Troubleshooting**

### **MCP Server Not Found?**
```bash
# Check global npm packages
npm list -g --depth=0

# Reinstall if needed
npm uninstall -g @michaellatman/mcp-server-arxiv
npm install -g @michaellatman/mcp-server-arxiv
```

### **Permission Issues?**
```bash
# Fix npm permissions (macOS/Linux)
sudo chown -R $(whoami) $(npm config get prefix)/{lib/node_modules,bin,share}

# Or use npx instead of global install
npx @michaellatman/mcp-server-arxiv
```

### **Node.js Version Issues?**
```bash
# Check version (need 18+)
node --version

# Update Node.js
brew upgrade node  # macOS
```

## 📊 **Available MCP Research Servers**

### **ArXiv Servers:**
- `@michaellatman/mcp-server-arxiv` - Primary recommendation
- `@blazickjp/arxiv-mcp-server` - Alternative implementation  
- `arxiv-mcp-server` - Community version

### **Multi-Database Servers:**
- `mcp-server-research` - Multiple academic databases
- `mcp-server-pubmed` - Medical research papers
- `semantic-scholar-mcp` - Semantic Scholar integration

### **Installation Commands:**
```bash
# Install multiple servers for broader research coverage
npm install -g @michaellatman/mcp-server-arxiv
npm install -g mcp-server-pubmed  
npm install -g semantic-scholar-mcp
```

## 🎯 **Demo Benefits**

### **With Real MCP Integration:**
✅ **Authentic research results** from ArXiv API  
✅ **Real MCP protocol** communication  
✅ **Standardized tool interfaces**  
✅ **Growing MCP ecosystem** access  
✅ **Production-ready** implementation  

### **Demo Narrative:**
> "This demonstrates real Model Context Protocol integration - not mocked data. The same MCP servers work across any MCP-compatible AI framework."

## 🚀 **Next Steps**

1. **Install MCP servers** using commands above
2. **Restart your demo** application
3. **Test research-enhanced variation** in LaunchDarkly  
4. **Verify real research results** instead of mock data

Your demo now showcases **genuine MCP integration** with real academic research capabilities! 🎉