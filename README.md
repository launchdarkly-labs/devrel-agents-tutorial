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

## Get It Running in 5 Minutes

**Ready to see data-driven AI optimization in action?** 

### Prerequisites
- **Python 3.9+** with `uv` package manager ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **LaunchDarkly account** ([sign up for free](https://app.launchdarkly.com/signup)) your AI optimization control center
- **API keys** for Anthropic Claude and/or OpenAI GPT models we'll show you which one actually performs better

### Step 1: Install & Configure (2 minutes)

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

### Step 2: Add Your Documents (1 minute)

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

### Step 3: Build Your Knowledge Base (1 minute)

```bash
# Turn documents into searchable AI knowledge
uv run python initialize_embeddings.py
# Creates vector embeddings for RAG search
# Enables semantic understanding vs keyword matching
# Processes all PDFs in kb/ directory
```

### Step 4: Launch Your Multi-Agent System (1 minute)

```bash
# Terminal 1: Start the AI agents backend
uv run uvicorn api.main:app --reload --port 8001

# Terminal 2: Launch the chat interface  
uv run streamlit run ui/chat_interface.py
```

### Step 5: See It Work (1 minute)

1. **Open http://localhost:8501** 
2. **Ask**: "What is reinforcement learning?" (if using sample docs) OR ask about your specific documents
3. **Watch**: Multiple agents coordinate to search your knowledge base and provide an intelligent response
4. **Notice**: Real-time tool usage, model selection, and performance metrics in the sidebar

**✅ You now have a working multi-agent system that measures its own performance and can be optimized through LaunchDarkly without code changes.**

## Domain-Specific Examples

**Want to adapt this for your specific domain?** Here are proven use cases:

**Domain Examples:**
- **Legal**: contracts, case law, compliance guidelines
- **Healthcare**: protocols, research papers, care guidelines  
- **SaaS**: API docs, user guides, troubleshooting manuals
- **Financial**: policies, regulations, investment research
- **Education**: course materials, research papers, curricula

**To switch domains after initial setup:**

```bash
# 1. Replace documents
rm kb/*.pdf  # Clear existing
cp /path/to/your-domain-docs/*.pdf kb/

# 2. Rebuild knowledge base
uv run python initialize_embeddings.py --force

# 3. Test with domain-specific questions
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "What are our standard contract terms?"}'
```

**Test** different query types:
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "What are our standard contract terms?"}'
```

**✅ Checkpoint**: Your AI agents now have expertise in your specific business domain.

## Control Everything: LaunchDarkly AI Configs

Instead of hardcoding AI behavior, control everything through LaunchDarkly's dashboard.

### Create AI Configs

1. **LaunchDarkly Dashboard** → **AI Configs** → **Create New**
2. **Create three AI Configs** with these exact names:
   - `supervisor-agent`
   - `support-agent`
   - `security-agent`

### Configure Supervisor Agent
**AI Config: `supervisor-agent`**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are an AI supervisor that coordinates between security and support agents. Route requests efficiently and track workflow state.",
  "temperature": 0.1,
  "tools": [],
  "variationKey": "main"
}
```

### Configure Security Agent
**AI Config: `security-agent`**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a privacy and security agent. Detect PII and sensitive information. Flag any personal identifiers, financial data, or confidential information.",
  "temperature": 0.0,
  "tools": [],
  "variationKey": "pii-detection"
}
```

### Configure Support Agent (Multiple Variations)

This is where you create different service tiers:

**AI Config: `support-agent`**

**Variation 1: `free-tier`**
```json
{
  "model": {"name": "claude-3-haiku-20240307"},
  "instructions": "You are a helpful assistant for [YOUR COMPANY]. Provide basic answers using available documentation.",
  "tools": ["search_v1"],
  "variationKey": "free-tier"
}
```

**Variation 2: `pro-tier`**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are an expert [YOUR DOMAIN] assistant. Provide detailed, comprehensive answers using advanced search and analysis.",
  "tools": ["search_v2", "reranking"],
  "variationKey": "pro-tier"
}
```

**Variation 3: `enterprise-claude`**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a premium [YOUR DOMAIN] expert with access to comprehensive research tools.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "enterprise-claude"
}
```

**Variation 4: `enterprise-openai`** (for A/B testing)
```json
{
  "model": {"name": "gpt-4o"},
  "instructions": "You are a premium [YOUR DOMAIN] expert with access to comprehensive research tools.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "enterprise-openai"
}
```

### Set Up Targeting Rules

1. **Support-agent Config** → **Targeting** → **Create Rules**:

```
IF user.plan = "free" THEN serve "free-tier"
IF user.plan = "pro" THEN serve "pro-tier"
IF user.plan = "enterprise" AND user.country = "US" THEN serve 50% "enterprise-claude", 50% "enterprise-openai"
IF user.country IN ["DE", "FR", "GB"] THEN serve "regional-compliance"
```

**Test Your Configurations:**
```bash
# Test enterprise user
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_001",
    "message": "I need comprehensive research on this topic", 
    "user_context": {"plan": "enterprise", "country": "US"}
  }'
```

**✅ Checkpoint**: You can now control AI behavior through LaunchDarkly without deployments.

## Add External Tools: MCP Integration

### Academic Research Tools (Built-in)

```bash
# Install ArXiv MCP Server
uv tool install arxiv-mcp-server

# Install Semantic Scholar MCP Server  
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git /tmp/semantic-scholar-server
uv add requests beautifulsoup4 mcp semanticscholar
```

**Test**: Ask "Find recent papers on transformer architectures" - should query both internal docs and external databases.

### Add Business MCP Tools

The system integrates with **any MCP server**. Browse the [MCP Server Directory](https://github.com/modelcontextprotocol/servers) for:

- **Developer Tools**: GitHub, GitLab, Jira, Slack
- **Business Systems**: Google Drive, Notion, Salesforce
- **Data Sources**: PostgreSQL, MongoDB, APIs

**Example: Add GitHub Integration**

1. **Install:**
```bash
npm install -g @modelcontextprotocol/server-github
```

2. **Configure:** Edit `tools_impl/mcp_research_tools.py`, add to `server_configs`:
```python
"github": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-github"]
}
```

3. **Enable in LaunchDarkly:** Add `"github"` to your AI Config tool lists
4. **Test:** Ask "Find authentication issues in our repository"

**Business Domain Examples:**

- **Legal**: `legal-research-mcp-server`, `case-law-mcp-server`
- **Healthcare**: `pubmed-mcp-server`, `medical-guidelines-mcp-server`
- **E-commerce**: `shopify-mcp-server`, `market-research-mcp-server`

**✅ Checkpoint**: Your agents can integrate with any business system through MCP.

## Run Experiments

Test which configurations work best for your use case.

### Set Up A/B Test

**Hypothesis**: Enhanced RAG increases satisfaction by 15% vs basic search.

1. **LaunchDarkly** → **Support-agent** → **Create Experiment**:
   - **Control**: `"tools": ["search_v1"]` 
   - **Treatment**: `"tools": ["search_v2", "reranking"]`

2. **Generate Test Data:**
```bash
python tools/traffic_generator.py --queries 100 --delay 1
```

3. **Monitor Results** in LaunchDarkly dashboard

**Example Results:**
| Variation | Satisfaction | Response Time | Cost |
|-----------|-------------|---------------|------|
| Basic Search | 72% | 1.2s | $0.05 |
| Enhanced RAG | 89% (+17%) | 1.8s | $0.075 |

**Decision**: Enhanced RAG wins! 17% satisfaction increase justifies 50% cost increase.

### Full-Stack Model Comparison: Claude vs OpenAI

**Hypothesis**: Claude provides better reasoning and tool usage efficiency than OpenAI for multi-agent workflows.

**1. Set Up Model Comparison Experiment:**

Use the existing `enterprise-claude` and `enterprise-openai` variations from your `support-agent` config:

- **Control (Claude)**: Uses all three agents (supervisor, security, support) with Claude models
- **Treatment (OpenAI)**: Uses identical agent workflow but with OpenAI models

**2. Update Your Variations for Fair Testing:**

**Claude Stack (Control):**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a premium expert with access to comprehensive research tools. Provide thorough analysis combining internal documentation with external research.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "full-stack-claude"
}
```

**OpenAI Stack (Treatment):**
```json
{
  "model": {"name": "gpt-4o"},
  "instructions": "You are a premium expert with access to comprehensive research tools. Provide thorough analysis combining internal documentation with external research.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "full-stack-openai"
}
```

**3. Configure 50/50 Split:**
```
IF user.plan = "enterprise" AND user.country = "US" THEN serve 50% "full-stack-claude", 50% "full-stack-openai"
```

**4. Run Extended Testing:**
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
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a privacy-focused security agent. Apply strict PII detection including: names, emails, phone numbers, addresses, IP addresses, device IDs. Flag any personal identifiers for removal. Err on the side of caution for data protection.",
  "temperature": 0.0,
  "tools": [],
  "variationKey": "eu-privacy-strict"
}
```

**US Standard Privacy Variation:**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a security agent focused on detecting sensitive PII including: SSNs, credit card numbers, banking information, medical records. Apply standard privacy measures while maintaining system functionality.",
  "temperature": 0.0,
  "tools": [],
  "variationKey": "us-standard-privacy"
}
```

**Targeting Rules for Security Agent:**
```
IF user.country IN ["DE", "FR", "IT", "GB"] THEN serve "eu-privacy-strict"
IF user.country = "US" AND user.state = "CA" THEN serve "us-standard-privacy"
IF user.region = "healthcare" THEN serve "eu-privacy-strict"
ELSE serve "us-standard-privacy"
```

**Support Agent Geographic Variations:**

**EU Model Selection:**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a helpful assistant. Prioritize user privacy in all responses. Avoid storing or referencing personal information.",
  "tools": ["search_v2", "reranking"],
  "variationKey": "eu-privacy-focused"
}
```

**US Enterprise Variation:**
```json
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are a premium expert with access to comprehensive research tools.",
  "tools": ["search_v2", "reranking", "arxiv_search", "semantic_scholar"],
  "variationKey": "us-full-featured"
}
```

**Usage-Based Tiers:**
```
IF user.monthly_usage < 1000 THEN serve "free-tier"
IF user.monthly_usage > 5000 THEN serve "pro-tier" 
IF user.contract_value > 50000 THEN serve "enterprise-tier"
```

**Time-Based Rules:**
```
IF current_time.hour BETWEEN 9 AND 17 THEN serve "business-hours" (expensive tools)
IF current_time.hour BETWEEN 17 AND 9 THEN serve "cost-optimized"
```

### Cost Management

**Tool Access by Tier:**
```json
{
  "free": ["search_v1"],                                  // $0.01/query
  "pro": ["search_v2", "reranking"],                     // $0.05/query
  "enterprise": ["search_v2", "reranking", "mcp_tools"]  // $0.25/query
}
```

**✅ Checkpoint**: Fine-grained control over AI behavior, costs, and compliance.

## Troubleshooting

**MCP Connection Issues:**
```bash
# Check MCP server installation
which arxiv-mcp-server

# Test server directly
/path/to/arxiv-mcp-server --help
```

**LaunchDarkly Issues:**
```bash
# Verify SDK key
echo $LD_SDK_KEY

# Check AI Configs exist in dashboard
```

**Knowledge Base Issues:**
```bash
# Rebuild embeddings
uv run python initialize_embeddings.py --force

# Test search
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "test query"}'
```

**Environment Check:**
```bash
uv run python -c "
import openai, anthropic, faiss, streamlit
print('All dependencies installed')
"
```

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