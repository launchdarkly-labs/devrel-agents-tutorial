# Level Up Your Multi-Agent System: Geographic + Business Tier Targeting with LaunchDarkly and MCP Tools

## Overview

Your multi-agent system works perfectly in testing, but what happens when enterprise customers expect premium models while free users need cost limits? Or when you need to handle EU privacy requirements? Suddenly you're facing dozens of configuration variations.

*Part 2 of 3 of the series: **Chaos to Clarity: Defensible AI Systems That Deliver on Your Goals***

The solution? **LangGraph multi-agent workflows** controlled by **LaunchDarkly AI Config** targeting rules that intelligently route users: paid customers get premium tools and models, free users get cost-efficient alternatives, and EU users get Claude for enhanced privacy. Deploy this complex matrix through smart configuration in minutes instead of hours.

## What You'll Build Today

In the next 18 minutes, you'll transform your basic multi-agent system with:

- **Business Tiers & MCP Integration**: Free users get internal RAG search, Paid users get premium models with external research tools and expanded tool call limits, all controlled by LaunchDarkly AI Configs
- **Geographic Targeting**: EU users automatically get Claude models (enhanced privacy), other users get cost-optimized alternatives
- **Smart Configuration**: Deploy complex targeting matrices with LaunchDarkly segments and targeting rules

## Prerequisites

You'll need:
- **Completed [Part 1](README.md)**: Working multi-agent system with basic AI Configs
- **Same environment**: Python 3.9+, uv, API keys from [Part 1](README.md)
- **LaunchDarkly API key**: Add `LD_API_KEY=your-api-key` to your `.env` file ([get API key](https://app.launchdarkly.com/settings/authorization))

## Step 1: Install MCP Servers (4 minutes)

**What is MCP?** [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) provides standardized connections between AI assistants and external data sources. Think of it as APIs specifically designed for AI tools - your agents can search academic papers, citation databases, or connect to various databases and services. MCP tools run as separate servers that your agents call when needed.

The [MCP Registry](https://github.com/modelcontextprotocol/registry) serves as a community-driven directory for discovering available MCP servers - like an "app store" for MCP tools. Browse available servers at [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io/docs#/operations/list-servers) to see what's currently available. Registry servers install through standard package managers:

```bash
# Example registry installations (not used in this tutorial)
pip install reddit-research-mcp    # Reddit research with citations  
npx scorecard-ai-mcp               # LLM evaluation tools
```

**Our Approach:** For this tutorial, we'll use manual installation since our specific academic research servers (ArXiv and Semantic Scholar) aren't yet available in the registry.

Install external research capabilities:

```bash
# Install ArXiv MCP server for academic paper search
uv tool install arxiv-mcp-server

# Install Semantic Scholar MCP server for citation data  
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git
```

**MCP Tools Added:**
- **arxiv_search**: Live academic paper search (Paid users)
- **semantic_scholar**: Citation and research database (Paid users)

These tools integrate with your agents via LangGraph - LaunchDarkly controls which users get access to which tools.

## Step 2: Deploy with API Automation (2 minutes)

Now that you have the tools created manually, we'll use programmatic API automation to deploy the complex targeting matrix. The LaunchDarkly REST API lets you manage segments and AI Configs programmatically. Instead of manually creating dozens of variations in the UI, you'll deploy complex targeting matrices with a single Python script. This approach is essential when you need to handle multiple geographic regions × business tiers with conditional tool assignments.

Deploy your complete targeting matrix with one command:

```bash
cd bootstrap
uv run python create_configs.py
```

This creates:
- **4 combined user segments** with geographic and tier targeting rules  
- **3 AI configs** with intelligent handling:
  - **supervisor-agent**: Skipped if already exists from Part 1 (identical configuration)
  - **security-agent**: Updated with 2 new geographic variations (basic vs strict GDPR)
  - **support-agent-business-tiers**: New config with 5 variations (geographic × tier matrix)
- **Complete targeting rules** that route users to appropriate variations

**Smart Resource Management**: The bootstrap script intelligently handles existing resources from Part 1:
- **Reuses**: `supervisor-agent` (identical), `support-agent` with `search_v2` and `reranking` tools 
- **Updates**: `security-agent` with geographic compliance variations
- **Creates New**: `support-agent-business-tiers` for business tier targeting, references your manually created tools (`search_v1`, `arxiv_search`, `semantic_scholar`)

## Step 3: Understand the Segmentation Strategy (2 minutes)

The bootstrap script created 4 combined user segments for precise targeting:

### Combined Segments (Geography + Business Tier)

The bootstrap script created 4 combined user segments for precise targeting. European users on free plans receive Claude Haiku with basic search capabilities only, while European users on paid plans get Claude Sonnet with full MCP research tools. Non-EU users on free plans are served GPT-4o Mini with basic search only, and non-EU users on paid plans receive GPT-4 with complete MCP research tools.

This segmentation strategy works by optimizing costs through efficient models for free users while providing premium capabilities to paid users. Additionally, it enhances privacy by giving EU users Anthropic Claude models with a privacy-by-design approach.

## Step 4: Test Segmentation with Script (2 minutes)

The included test script simulates real user scenarios across all segments, verifying that your targeting rules work correctly. It sends actual API requests to your system and confirms each user type gets the right model, tools, and behavior - giving you confidence before real users arrive.

Validate your segmentation with the test script:

```bash
uv run python tests/test_tutorial_2.py
```

This confirms your targeting matrix is working correctly across all user segments.

## Step 5: Experience Segmentation in the Chat UI (3 minutes)

Now let's see your segmentation in action through the actual user interface that your customers will experience.

```bash
# Start your system (2 terminals)
uv run uvicorn api.main:app --reload --port 8000
uv run streamlit run ui/chat_interface.py --server.port 8501
```

Open http://localhost:8501 and test different user types:

1. **User Dropdown**: Select different countries (Germany, France, US) and plans (Free, Paid)
2. **Ask Questions**: Try "Search for machine learning papers" 
3. **Watch Workflow**: See which model and tools get used for each user type
4. **Verify Routing**: EU users get Claude, Other users get GPT, Paid users get MCP tools

<div align="center">

![Chat Interface User Selection](screenshots/chat_interface_user_dropdown.png)
*Select different user types to test segmentation in the chat interface*

</div>

## What You've Accomplished

You've built a sophisticated multi-agent system that demonstrates how modern AI applications can handle complex user segmentation and feature differentiation. The combination of manual tool creation and automated configuration deployment shows a practical approach to managing multi-dimensional targeting without overwhelming operational complexity. This foundation provides a clear framework for expanding into additional geographic regions or business tiers as needed.

Your multi-agent system now has:
- **Smart Geographic Routing**: Enhanced privacy protection for EU users
- **Business Tier Management**: Feature scaling that grows with customer value
- **API Automation**: Complex configurations deployed programmatically
- **External Tool Integration**: Research capabilities for premium users

## What's Next: Part 3 Preview

**In Part 3**, we'll prove what actually works using A/B experiments:

### **Experimentation Strategy**  
- **Model Performance**: Test Claude vs GPT-4 conversion rates by region
- **Tool Effectiveness**: Measure RAG vs MCP impact on user satisfaction
- **Tier Optimization**: Find the perfect cost/value balance between Free and Paid tiers

### **Real Metrics**
- User engagement by geographic segment
- Conversion rates from Free → Paid  
- Cost per query vs user satisfaction scores
- Tool usage patterns that predict upgrades

Instead of guessing what users want, you'll have data proving which configurations drive real business results.

---

*Ready for data-driven optimization? Part 3 will show you how to run experiments that prove ROI and guide product decisions with real user behavior data.*