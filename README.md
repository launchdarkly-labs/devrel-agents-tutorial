# Stop Guessing. Start Measuring. Build AI Systems That Optimize Themselves.

*Transform AI development from expensive trial-and-error into data-driven engineering with LaunchDarkly AI Configs*

## Overview

Here's what's broken about AI development right now: You spend weeks building an AI system, only to discover GPT-4 is too expensive, Claude might be better for your use case, and European users need different privacy handling. Making changes means code deploys, testing cycles, and crossing your fingers.

**Meanwhile, your competitors are shipping faster because they solved this problem.**

This tutorial shows you how to build AI systems the smart way. Instead of hardcoding everything, you'll create **LangGraph multi-agent workflows** that get their intelligence from **RAG search** through your business documents, enhanced with **MCP tools** for live external data, all controlled dynamically through **LaunchDarkly AI Configs**.

**The result?** Change models, adjust privacy settings, or add new tools with a few clicks. Test everything with real A/B experiments. Make AI decisions backed by actual data instead of developer intuition.

You'll build a robust system that adapts to users in real-time while giving you the metrics to prove what actually works for your business.

## What You'll Build: A Self-Optimizing AI System

**In 20 minutes**, you'll have a production-ready multi-agent system that **measures and improves itself**:

### **Immediate Value**
- **Multi-agent orchestration**: Supervisor, security, and support agents working together
- **Your domain expertise**: RAG search through your business documents 
- **Live external data**: MCP integration with academic databases, GitHub, business APIs
- **Zero-downtime configuration**: Change models, tools, and behavior through LaunchDarkly dashboard

**Instead of guessing which configuration works, you'll have data proving which one delivers better outcomes at lower cost.**

## Quick Start Guide

**Ready to see data-driven AI optimization in action?** 

### Prerequisites
- **Python 3.9+** with `uv` package manager ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **LaunchDarkly account** ([sign up for free](https://app.launchdarkly.com/signup)) your AI optimization control center
- **API keys** for Anthropic Claude and/or OpenAI GPT models we'll show you which one actually performs better

### Step 1: Set Up Your Tools in LaunchDarkly (3 minutes)

**First, create your tool definitions in LaunchDarkly Dashboard → Tools → Create New Tool:**

**Tool 1: Keyword Search (created in repo)**
```json
{
  "name": "search_v1",
  "displayName": "Basic Document Search",
  "description": "Performs keyword-based search through uploaded documents using BM25 scoring",
  "parameters": {
    "query": {
      "type": "string",
      "description": "The search query to find relevant documents"
    }
  }
}
```

**Tool 2: Advanced RAG Search (created in repo)**
```json
{
  "name": "search_v2", 
  "displayName": "RAG Vector Search",
  "description": "Advanced semantic search using vector embeddings for contextual document retrieval",
  "parameters": {
    "query": {
      "type": "string",
      "description": "The search query for semantic document matching"
    },
    "top_k": {
      "type": "integer",
      "description": "Number of most relevant documents to return",
      "default": 5
    }
  }
}
```

**Tool 3: Result Reranking (created in repo)**
```json
{
  "name": "reranking",
  "displayName": "Search Result Reranker", 
  "description": "Improves search results by reordering based on semantic relevance to the query",
  "parameters": {
    "query": {
      "type": "string", 
      "description": "Original search query for relevance scoring"
    },
    "results": {
      "type": "array",
      "description": "Search results to rerank for improved relevance"
    }
  }
}
```

**Tool 4: ArXiv Search (MCP)**
```json
{
  "name": "arxiv_search",
  "displayName": "ArXiv Academic Search",
  "description": "Search academic papers from ArXiv database with advanced filtering",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Research query to search ArXiv papers"
    },
    "max_results": {
      "type": "integer", 
      "description": "Maximum number of papers to return",
      "default": 10
    }
  }
}
```

**Tool 5: Semantic Scholar (MCP)**
```json
{
  "name": "semantic_scholar",
  "displayName": "Semantic Scholar Research",
  "description": "Search academic papers with citation analysis via Semantic Scholar API",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Academic research query"  
    },
    "fields": {
      "type": "array",
      "description": "Paper fields to include (title, abstract, citations, etc.)",
      "default": ["title", "abstract", "year", "citationCount"]
    }
  }
}
```

**✅ Checkpoint**: Your tools are now defined and ready to use in AI Configs.

### Step 2: Set Up LaunchDarkly AI Configs (2 minutes)

**Now let's set up your AI agents in LaunchDarkly.** This is where the magic happens - you'll control your entire AI system from here:

1. **LaunchDarkly Dashboard** → **AI Configs** → **Create New**
2. **Create three AI Configs** with these exact names:
   - `supervisor-agent`
   - `support-agent` 
   - `security-agent`

**Quick Setup Configs:**

**AI Config: `supervisor-agent`**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are an AI supervisor that coordinates between security and support agents. Route requests efficiently and track workflow state.",
  "tools": [],
  "variationKey": "supervisor-basic",
  "customParameters": {
    "max_cost": 0.5,
    "max_tool_calls": 3,
    "workflow_type": "supervisor"
  }
}
```

**AI Config: `security-agent`**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a privacy and security agent. Detect PII and sensitive information. Flag any personal identifiers, financial data, or confidential information.",
  "tools": [],
  "variationKey": "pii-basic",
  "customParameters": {
    "max_cost": 0.25,
    "max_tool_calls": 2,
    "workflow_type": "security"
  }
}
```

**AI Config: `support-agent`** (Start with basic version)
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in comprehensive research. Use all available tools strategically to provide thorough, well-researched responses.",
  "tools": ["search_v2", "reranking"],
  "variationKey": "search-only-v2",
  "customParameters": {
    "max_cost": 1,
    "max_tool_calls": 8,
    "workflow_type": "conditional"
  }
}
```
✅ Checkpoint: Your AI agents now have roles and tools.

### Step 3: Install & Configure Code (2 minutes)

```bash
git clone https://github.com/launchdarkly/agents-demo.git
cd agents-demo
uv sync  # Installs all dependencies including LangGraph, MCP tools, and LaunchDarkly SDK

# Configure your AI optimization environment
cp .env.example .env
# Edit .env with your keys:
# - LD_SDK_KEY (enables real-time AI configuration)
# - ANTHROPIC_API_KEY (from console.anthropic.com) 
# - OPENAI_API_KEY (from platform.openai.com) optional but enables A/B testing
```

### Step 4: Add Your Documents (1 minute)

**Want to adapt this for your specific domain?** Here are proven use cases:

**Domain Examples:**
- **Legal**: contracts, case law, compliance guidelines
- **Healthcare**: protocols, research papers, care guidelines  
- **SaaS**: API docs, user guides, troubleshooting manuals
- **Financial**: policies, regulations, investment research
- **Education**: course materials, research papers, curricula

```bash
# Option A: Start with sample content (AI/ML knowledge base)
# Sample document already included: kb/SuttonBartoIPRLBook2ndEd.pdf

# Option B: Use YOUR business documents instead
rm kb/SuttonBartoIPRLBook2ndEd.pdf  # Remove sample
# Add your domain-specific documents:
cp /path/to/your-company-handbook.pdf kb/
cp /path/to/your-product-docs.pdf kb/
cp /path/to/your-legal-policies.pdf kb/
```
**✅ Checkpoint**: Your AI agents now have expertise in your specific business domain.

### Step 5: Build Your Knowledge Base (1 minute)

```bash
# Turn documents into searchable AI knowledge
uv run python initialize_embeddings.py
# Creates vector embeddings for RAG search
# Enables semantic understanding vs keyword matching
# Processes all PDFs in kb/ directory
```

### Step 6: Launch Your Multi-Agent System (1 minute)

```bash
# Terminal 1: Start the AI agents backend
uv run uvicorn api.main:app --reload --port 8001

# Terminal 2: Launch the chat interface  
uv run streamlit run ui/chat_interface.py
```

### Step 7: See It Work (1 minute)

1. **Open http://localhost:8501** 
2. **Ask**: "What is reinforcement learning?" (if using sample docs) OR ask about your specific documents
3. **Watch**: Multiple agents coordinate to search your knowledge base and provide an intelligent response
4. **Notice**: Real-time tool usage, model selection, and performance metrics in the sidebar

**✅ You now have a working multi-agent system that measures its own performance and can be optimized through LaunchDarkly without code changes.**

## Advanced AI Config Setup: Business Tiers & A/B Testing

Now that your system is running, you can create sophisticated configurations for different user segments and A/B testing.

### Configure Support Agent Business Tiers

Add multiple variations to your existing `support-agent` config for different service tiers:

**Variation 1: No Tools (Basic)**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant. Provide basic responses using only your training knowledge.",
  "tools": [],
  "variationKey": "no-tools",
  "customParameters": {
    "max_cost": 0.1,
    "max_tool_calls": 0,
    "workflow_type": "basic"
  }
}
```

**Variation 2: Search Only v1 (Keyword)**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant. Use basic keyword search through documentation when needed.",
  "tools": ["search_v1"],
  "variationKey": "search-only-v1",
  "customParameters": {
    "max_cost": 0.5,
    "max_tool_calls": 4,
    "workflow_type": "search-basic"
  }
}
```

**Variation 3: Full Research Claude**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in comprehensive research. Use all available tools strategically to provide thorough, well-researched responses.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "full-research-claude",
  "customParameters": {
    "max_cost": 1,
    "max_tool_calls": 8,
    "workflow_type": "conditional"
  }
}
```

**Variation 4: Full Research OpenAI** (for A/B testing)
```json
{
  "model": {"name": "chatgpt-4o-latest"},
  "instructions": "You are a helpful AI assistant specialized in comprehensive research. Use all available tools strategically to provide thorough, well-researched responses.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "full-research-openai",
  "customParameters": {
    "max_cost": 1,
    "max_tool_calls": 8,
    "workflow_type": "conditional"
  }
}
```

### Set Up Targeting Rules

1. **Support-agent Config** → **Targeting** → **Create Rules**:

```
IF user.plan = "free" THEN serve "no-tools"
IF user.plan = "basic" THEN serve "search-only-v1"
IF user.plan = "pro" THEN serve "search-only-v2"
IF user.plan = "enterprise" AND user.country = "US" THEN serve 50% "full-research-claude", 50% "full-research-openai"
IF user.country IN ["DE", "FR", "GB"] THEN serve "full-research-claude"
```

**Test Your Configurations:**
```bash
# Test enterprise user
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_001",
    "message": "I need comprehensive research on transformer architectures", 
    "user_context": {"plan": "enterprise", "country": "US"}
  }'
```

**✅ Checkpoint**: You can now control AI behavior through LaunchDarkly without deployments.

## Add External Tools: MCP Integration

**Note**: You already created the MCP tool definitions (`arxiv_search`, `semantic_scholar`) in Step 1. Now you need to install the actual MCP servers and enable the tools in your AI Configs.

### Academic Research Tools (Built-in)

**1. Install the MCP Servers:**
```bash
# Install ArXiv MCP Server
uv tool install arxiv-mcp-server

# Install Semantic Scholar MCP Server  
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/semantic-scholar-server
uv add requests beautifulsoup4 mcp semanticscholar
```

**2. Enable in LaunchDarkly AI Configs:**
Go to your `support-agent` AI Config and add the MCP tools to the tools array:
```json
{
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"]
}
```

**Test**: Ask "Find recent papers on transformer architectures" - should query both internal docs and external databases.

### Add Business MCP Tools

The system integrates with **any MCP server**. Browse the [MCP Server Directory](https://github.com/modelcontextprotocol/servers) for:

- **Developer Tools**: GitHub, GitLab, Jira, Slack
- **Business Systems**: Google Drive, Notion, Salesforce
- **Data Sources**: PostgreSQL, MongoDB, APIs

**Example: Add GitHub Integration**

**1. Create Tool Definition in LaunchDarkly:**
```json
{
  "name": "github_search",
  "displayName": "GitHub Repository Search", 
  "description": "Search code, issues, and repositories on GitHub",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query for GitHub repositories and code"
    },
    "type": {
      "type": "string", 
      "description": "Type of search: code, issues, repositories",
      "default": "code"
    }
  }
}
```

**2. Install MCP Server:**
```bash
npm install -g @modelcontextprotocol/server-github
```

**3. Configure Server:** Edit `tools_impl/mcp_research_tools.py`, add to `server_configs`:
```python
"github": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-github"]
}
```

**4. Enable in AI Config:** Add `"github_search"` to your `support-agent` tools array:
```json
{
  "tools": ["search_v2", "reranking", "github_search"]
}
```

**5. Test:** Ask "Find authentication issues in our repository"

**Business Domain Examples:**

- **Legal**: `legal-research-mcp-server`, `case-law-mcp-server`
- **Healthcare**: `pubmed-mcp-server`, `medical-guidelines-mcp-server`
- **E-commerce**: `shopify-mcp-server`, `market-research-mcp-server`

**✅ Checkpoint**: Your agents can integrate with any business system through MCP.

## Run Experiments

Test which configurations work best for your use case.

### Experiment 1: Search Implementation Comparison

**Hypothesis**: Enhanced RAG increases satisfaction by 15% vs basic search.

**1. Set Up Search Implementation Experiment:**

Use the existing `search-only-v1` and `search-only-v2` variations from your `support-agent` config:

- **Control (Basic Search)**: Uses keyword-based search through documents
- **Treatment (Enhanced RAG)**: Uses vector embeddings with semantic reranking

**2. Generate Test Data:**
```bash
python tools/traffic_generator.py --queries 200 --delay 1
```

**Example Results After 200 Queries:**
| Search Method | Satisfaction | Avg Response Time | Token Usage | Tool Calls | Cost per Query |
|---------------|-------------|------------------|-------------|------------|----------------|
| Basic Search | 72% | 1.2s | 1,200 tokens | 2.1 avg | $0.05 |
| Enhanced RAG | 89% | 1.8s | 1,650 tokens | 2.8 avg | $0.075 |

**Key Insights:**
- **Enhanced RAG**: Higher satisfaction, better semantic understanding, moderate cost increase
- **Basic Search**: Faster response time, lower cost, but less accurate results
- **Winner**: Enhanced RAG provides better value with 17% higher satisfaction justifying 50% cost increase

**Decision**: Deploy Enhanced RAG as default for all users. The 17% satisfaction increase and better semantic understanding outweigh the moderate cost increase.

### Experiment 2: Model Comparison

**Hypothesis**: Claude provides better reasoning and tool usage efficiency than OpenAI for multi-agent workflows.

**1. Set Up Model Comparison Experiment:**

Use the existing `full-research-claude` and `full-research-openai` variations from your `support-agent` config:

- **Control (Claude)**: Uses comprehensive research tools with Claude models
- **Treatment (OpenAI)**: Uses identical tools with OpenAI models

**2. Generate Test Data:**
```bash
# Generate more data for statistical significance
python tools/traffic_generator.py --queries 200 --delay 1
```

**Example Results After 200 Queries:**
| Model Stack | Satisfaction | Avg Response Time | Token Usage | Tool Calls | Cost per Query |
|-------------|-------------|------------------|-------------|------------|----------------|
| Claude Full-Stack | 91% | 2.1s | 1,850 tokens | 3.2 avg | $0.12 |
| OpenAI Full-Stack | 87% | 1.8s | 2,200 tokens | 4.1 avg | $0.15 |

**Key Insights:**
- **Claude**: Higher satisfaction, more efficient tool usage, lower cost
- **OpenAI**: Faster response time, but uses more tokens and tool calls
- **Winner**: Claude provides better value with 4% higher satisfaction and 20% lower cost

**Decision**: Deploy Claude as default for enterprise users, keep OpenAI as fallback for speed-critical applications.

**✅ Checkpoint**: You're making data-driven AI decisions.

## Advanced Customization

### Swapping Out Your Knowledge Base Documents

**Ready to change domains or add more documents?** Here's how to update your knowledge base with different content:

**Best document formats:**
- **PDF**: Contracts, research papers, manuals, policies (recommended)
- **Text**: Documentation, guides, FAQs
- **Markdown**: Technical docs, wikis

```bash
# 1. Stop the system if it's running
# Ctrl+C in both terminal windows

# 2. Clear existing documents and embeddings
rm kb/*.pdf
rm -rf embeddings_store/  # Remove old vector embeddings

# 3. Add your new documents
cp /path/to/your-new-documents/*.pdf kb/

# 4. Rebuild the knowledge base
uv run python initialize_embeddings.py

# 5. Restart the system
# Terminal 1:
uv run uvicorn api.main:app --reload --port 8001
# Terminal 2: 
uv run streamlit run ui/chat_interface.py

# 6. Test with domain-specific queries
# Legal: "What are our standard contract terms?"
# Healthcare: "What is the protocol for patient intake?"  
# Software: "How do I authenticate API requests?"
```

### Domain-Specific Instructions

Replace generic instructions with your domain expertise:

**Customer Support:**
```json
{
  "instructions": "You are a customer support specialist for [COMPANY]. Help with account issues, billing, and troubleshooting. Check our knowledge base first, escalate appropriately."
}
```

**Legal Research:**
```json
{
  "instructions": "You are a legal research assistant. Find case law, statutes, and precedents. Cite accurately, highlight jurisdictional differences. Never provide legal advice, only research."
}
```

**Medical Information:**
```json
{
  "instructions": "You are a medical information assistant for healthcare professionals. Provide evidence-based information with citations. Include contraindications and safety considerations."
}
```

### Advanced Targeting

**Geographic-Based Security Configuration:**

Create multiple security agent variations for different regions by adding variations to your `security-agent` AI Config:

**EU Privacy-Focused Variation:**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a privacy-focused security agent. Apply strict PII detection including: names, emails, phone numbers, addresses, IP addresses, device IDs. Flag any personal identifiers for removal. Err on the side of caution for data protection.",
  "tools": [],
  "variationKey": "eu-privacy-strict",
  "customParameters": {
    "max_cost": 0.25,
    "max_tool_calls": 2,
    "workflow_type": "security-strict"
  }
}
```

**US Standard Privacy Variation:**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a security agent focused on detecting sensitive PII including: SSNs, credit card numbers, banking information, medical records. Apply standard privacy measures while maintaining system functionality.",
  "tools": [],
  "variationKey": "us-standard-privacy",
  "customParameters": {
    "max_cost": 0.25,
    "max_tool_calls": 2,
    "workflow_type": "security-standard"
  }
}
```

**Targeting Rules for Security Agent:**
```
IF user.country IN ["DE", "FR", "IT", "GB"] THEN serve "eu-privacy-strict"
IF user.country = "US" THEN serve "us-standard-privacy"
IF user.region = "healthcare" THEN serve "eu-privacy-strict"
ELSE serve "us-standard-privacy"
```

**Support Agent Geographic Variations:**

**EU Model Selection:**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful assistant. Prioritize user privacy in all responses. Avoid storing or referencing personal information.",
  "tools": ["search_v2", "reranking"],
  "variationKey": "eu-privacy-focused",
  "customParameters": {
    "max_cost": 0.75,
    "max_tool_calls": 6,
    "workflow_type": "privacy-first"
  }
}
```

**US Enterprise Variation:**
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a premium expert with access to comprehensive research tools.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "us-full-featured",
  "customParameters": {
    "max_cost": 1,
    "max_tool_calls": 8,
    "workflow_type": "full-featured"
  }
}
```

**Usage-Based Tiers:**
```
IF user.monthly_usage < 1000 THEN serve "no-tools"
IF user.monthly_usage > 5000 THEN serve "search-only-v2" 
IF user.contract_value > 50000 THEN serve "full-research-claude"
```

**Time-Based Rules:**
```
IF current_time.hour BETWEEN 9 AND 17 THEN serve "full-research-claude"
IF current_time.hour BETWEEN 17 AND 9 THEN serve "search-only-v2"
```

### Cost Management

**Tool Access by Tier:**
```json
{
  "free": [],                                             // $0.001/query
  "basic": ["search_v1"],                                 // $0.01/query
  "pro": ["search_v2", "reranking"],                     // $0.05/query
  "enterprise": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"]  // $0.25/query
}
```

**✅ Checkpoint**: Fine-grained control over AI behavior, costs, and compliance.


---

## What You've Built: The Components of a Self-Optimizing AI System

### **Multi-Agent Intelligence Architecture**
- **Supervisor Agent**: Orchestrates workflow between specialized agents with state management
- **Security Agent**: PII detection with geographic targeting (GDPR/CCPA compliance)
- **Support Agent**: Your domain expertise + live external research capabilities

### **Intelligent Search & Knowledge Stack**
- **RAG Search**: Vector embeddings of your documents + semantic reranking for contextual understanding
- **MCP Integration**: Live external data from academic databases, GitHub, business APIs
- **Cost-Optimized Deployment**: Expensive research tools only deployed when they add genuine value

### **Data-Driven Optimization Engine**  
- **A/B Testing Platform**: Compare model performance, tool effectiveness, and cost efficiency with statistical significance
- **Real-time Configuration**: Switch models, adjust tool access, modify behavior through LaunchDarkly dashboard
- **Business Logic Integration**: Different user segments get different AI capabilities automatically

### **Performance Measurement & Control**
- **Success Rate Tracking**: Which configurations actually resolve user queries
- **Cost Attribution**: Measure per-query costs across different model and tool combinations  
- **Latency Optimization**: Performance data guides model selection and tool deployment decisions

**The key difference**: Instead of building AI systems that you hope work well, you've built one that *proves* it works well and continuously optimizes itself based on real user data.

## Next Steps

- **Custom UI**: React/Vue frontend matching your brand
- **Advanced Targeting**: Behavior-based model selection


## Resources

- **[LaunchDarkly AI Configs](https://docs.launchdarkly.com/guides/flags/ai-configs)**
- **[MCP Server Directory](https://github.com/modelcontextprotocol/servers)**
- **[LangGraph Documentation](https://langchain-ai.github.io/langgraph/)**

Questions? Reach out at `aiproduct@launchdarkly.com`