# LaunchDarkly AI Config Multi-Agent Demo

An advanced tutorial demonstrating LaunchDarkly AI Config with multi-agent workflows, RAG, and MCP integration.

## Features

- **Multi-Agent Architecture**: Supervisor orchestrates Security and Research agents
- **LaunchDarkly AI Config**: Runtime control of 3 specialized agents 
- **RAG Integration**: Vector search with embeddings, FAISS, and BM25 reranking
- **MCP Integration**: ArXiv and Semantic Scholar via Model Context Protocol
- **Multi-Provider Support**: Claude and OpenAI models

## Quick Start

### Prerequisites
- Python 3.11+ (required for MCP integration)
- [uv](https://astral.sh/uv/) package manager
- Node.js 18+ (for MCP servers)
- OpenAI API key (for vector embeddings)
- Anthropic API key (for Claude models)
- LaunchDarkly SDK key (for AI configs)

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
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git
uv add requests beautifulsoup4 mcp semanticscholar

```

4. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your API keys:
# LD_SDK_KEY=your-launchdarkly-sdk-key
# ANTHROPIC_API_KEY=your-anthropic-api-key
# OPENAI_API_KEY=your-openai-api-key
```

5. **Initialize vector embeddings** (one-time setup):
```bash
uv run initialize_embeddings.py
```
This creates persistent OpenAI embeddings from your knowledge base. Run with `--force` to recreate embeddings.

## Knowledge Base Management

The system includes a persistent vector database for RAG (Retrieval-Augmented Generation) capabilities. Here's how to manage your knowledge base:

### Adding Documents

1. **Add PDF files** to the `kb/` directory:
```bash
# Add your PDFs to the knowledge base directory
cp your-document.pdf kb/
cp another-document.pdf kb/
```

2. **Recreate embeddings** to include the new documents:
```bash
uv run initialize_embeddings.py --force
```

**Note**: The system automatically detects all PDF files in the `kb/` directory. No code changes required!

### Removing Documents

1. **Remove PDF files** from the `kb/` directory:
```bash
rm kb/unwanted-document.pdf
```

2. **Recreate embeddings** to update the database:
```bash
uv run initialize_embeddings.py --force
```

### Knowledge Base Commands

```bash
# Initialize embeddings (first time only)
uv run initialize_embeddings.py

# Force recreate all embeddings (after adding/removing documents)
uv run initialize_embeddings.py --force

# Check current embeddings status
ls -la data/vector_store/

# View current knowledge base contents
ls -la kb/

# Test knowledge base loading
uv run python -c "from data.enterprise_kb import get_knowledge_base; kb = get_knowledge_base(); print(f'Loaded {len(kb)} chunks from KB')"
```

### Supported Document Types

Currently supports:
- ✅ **PDF files** - Automatically processed and chunked
- 📋 **Future**: Plain text, Markdown, Word documents

### Vector Database Details

- **Storage**: `data/vector_store/` directory
- **Embeddings**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Vector DB**: FAISS with cosine similarity
- **Persistence**: Embeddings stored on disk, loaded automatically
- **Chunking**: Smart text chunking with overlap for better retrieval

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
- `utils/` - Performance utilities
- `config_manager.py` - LaunchDarkly AI Config management with caching
- `ui/` - Streamlit chat interface
- `docs/` - MCP Research Integration Guide (setup and troubleshooting)

## Configuration

### **LaunchDarkly AI Configs:**
The system uses **3 specialized AI Config flags**:

- `supervisor-agent`: Controls workflow routing logic
- `security-agent`: Manages PII detection behavior  
- `support-agent`: Controls RAG and research tool availability

### **Support Agent Variations:**
- **`docs-only`**: Basic search only (`["search_v2"]`)
- **`rag-enabled`**: Full RAG stack with BM25 reranking (`["search_v2", "reranking"]`)
- **`research-enhanced`**: RAG + MCP research (`["search_v2", "reranking", "arxiv_search", "semantic_scholar"]`)

### **MCP Tools:**
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

## 🚀 Traffic Simulation for Experiments

Generate realistic traffic to test your LaunchDarkly AI Config variations and create compelling blog post metrics.

### Quick Traffic Generation

```bash
# Generate 50 queries with geographic users (basic)
python tools/traffic_generator.py --queries 50 --delay 2

# Generate 200 queries quickly (for blog post data)
python tools/traffic_generator.py --queries 200 --delay 0.5

# Verbose output to see details
python tools/traffic_generator.py --queries 20 --delay 1 --verbose
```

### What Gets Simulated

✅ **Real AI Responses**: Actual multi-agent workflows with real MCP tools  
✅ **Geographic Targeting**: Fake users from US, EU, Asia with different plans  
✅ **Realistic Feedback**: Smart rules simulate thumbs up/down based on response quality  
✅ **Real User Feedback**: UI includes thumbs up/down buttons for actual user feedback
✅ **LaunchDarkly Metrics**: Both real and simulated feedback flow to your dashboard  

### Example Output
```
🌍 USER CONTEXT: user_eu_enterprise_001 from DE on enterprise plan
🤖 SENDING: user asks 'Find recent papers on transformers...'
✅ SUCCESS: Got 1247 chars, used 2 tools
👍 FEEDBACK: user gave 👍 (rating: 4/5) - good length, found keywords, used tools
🚀 METRICS: Flushed to LaunchDarkly
```

### Files You Can Customize
- `data/fake_users.json` - Add users from different countries/plans
- `data/sample_queries.json` - Add questions specific to your domain  
- `tools/traffic_generator.py` - Adjust feedback simulation logic (edit the `simulate_feedback()` function)

**📚 Full Guide**: See [Traffic Simulation Guide](docs/TRAFFIC_SIMULATION_GUIDE.md) for complete instructions
