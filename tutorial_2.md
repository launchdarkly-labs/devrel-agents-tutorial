# Level Up Your Multi-Agent System: Geographic + Business Tier Targeting with LaunchDarkly API Automation and MCP Tools

## Overview

Your multi-agent system works perfectly in testing, but what happens when enterprise customers expect premium models while free users need cost limits? Or when you need to handle EU privacy requirements? Suddenly you're facing dozens of configuration variations.

*Part 2 of 3 of the series: **Chaos to Clarity: Defensible AI Systems That Deliver on Your Goals***

The solution? **LangGraph multi-agent workflows** controlled by **LaunchDarkly AI Config** targeting rules that intelligently route users: paid customers get premium tools and models, free users get cost-efficient alternatives, and EU users get Claude for enhanced privacy. Deploy this complex matrix through **LaunchDarkly API** automation in seconds instead of hours.

## What You'll Build Today

In the next 20 minutes, you'll transform your basic multi-agent system with:

- **Business Tiers & MCP Integration**: Free users get internal RAG search, Paid users get premium models with external research tools and expanded tool call limits, all controlled by LaunchDarkly AI Configs
- **Geographic Targeting**: EU users automatically get Claude models (enhanced privacy), other users get cost-optimized alternatives
- **API Automation**: Deploy complex targeting matrices with a single Python script instead of manual UI configuration

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

## Step 2: Setup LaunchDarkly API Dependencies (2 minutes)

Install the bootstrap system dependencies:

```bash
cd bootstrap
uv pip install -r requirements.txt
```

**Note:** If you've already run `uv sync` from the main project directory (from Part 1), you already have `requests` and `python-dotenv`. This step only adds `pyyaml` for parsing the configuration manifest.

**How the Bootstrap Works:**
The system uses the LaunchDarkly REST API to programmatically create:
- **4 user segments** (eu-free, eu-paid, other-free, other-paid) with combined geographic + business tier targeting rules
- **3 AI configs** with multiple variations each:
  - **Supervisor Agent**: 1 variation (reused from Part 1 if it exists)
  - **Security Agent**: 2 new variations replacing Part 1's single variation
    - `basic-security`: Non-EU users (allows names, job titles)
    - `strict-security`: EU users (GDPR compliant, redacts all PII)
  - **Support Agent Business Tiers**: New config with 5 variations (replaces Part 1's simple support-agent)
    - `eu-free`: Claude Haiku + basic search
    - `eu-paid`: Claude Sonnet + full RAG + MCP tools
    - `other-free`: GPT-4o Mini + basic search
    - `other-paid`: GPT-4 + full RAG + MCP tools
    - `international-standard`: Fallback variation
- **Targeting rules** that automatically route users to appropriate configurations based on location and plan type

All configurations are defined in `ai_config_manifest.yaml` and deployed via `create_configs.py` using direct API calls. This programmatic approach provides version-controlled infrastructure as code that can handle complex multi-dimensional targeting matrices that would be tedious to configure manually in the UI.

## Step 3: Understand the Segmentation Strategy (3 minutes)

Now that you have MCP tools installed, let's understand how they'll be distributed across different user segments.

Your automation script will create 4 combined user segments for precise targeting:

### Combined Segments (Geography + Business Tier)
- **EU Free**: European users on free plans - get Claude Haiku with basic search only
- **EU Paid**: European users on paid plans - get Claude Sonnet with full MCP research tools  
- **Other Free**: Non-EU users on free plans - get GPT-4o Mini with basic search only
- **Other Paid**: Non-EU users on paid plans - get GPT-4 with full MCP research tools

### Simplified Targeting Matrix

```
                │  Free           │  Paid
────────────────┼─────────────────┼─────────────────
EU Users        │  Claude Haiku   │  Claude Sonnet
                │  Basic Search   │  + Full MCP
Other Users     │  GPT-4o Mini    │  GPT-4  
                │  Basic Search   │  + Full MCP
```

**Why This Works:**
- **Cost Optimization**: Free users get efficient models, Paid users get premium capabilities
- **Simplified Management**: 4 segments instead of complex geographic × tier combinations
- **Enhanced Privacy**: EU users get Anthropic Claude models with privacy-by-design approach

## Step 4: Deploy with API Automation (2 minutes)

In [Part 1](README.md) you saw how easy it was to set up AI Configs through the [LaunchDarkly UI](https://app.launchdarkly.com). For complex multi-dimensional targeting, we'll use programmatic API automation. The LaunchDarkly REST API lets you manage segments, tools, and AI Configs programmatically. Instead of manually creating dozens of variations in the UI, you'll deploy complex targeting matrices with a single Python script. This approach is essential when you need to handle multiple geographic regions × business tiers with conditional tool assignments.

Deploy your complete targeting matrix with one command:

```bash
uv run python create_configs.py
```

This creates:
- **3 essential tools**: `search_v1` (basic search), `arxiv_search` (MCP), `semantic_scholar` (MCP)
- **4 combined user segments** with geographic and tier targeting rules  
- **3 AI configs** with intelligent handling:
  - **supervisor-agent**: Skipped if already exists from Part 1 (identical configuration)
  - **security-agent**: Updated with 2 new geographic variations (basic vs strict GDPR)
  - **support-agent-business-tiers**: New config with 5 variations (geographic × tier matrix)
- **Complete targeting rules** that route users to appropriate variations

**Smart Resource Management**: The bootstrap script intelligently handles existing resources from Part 1:
- **Reuses**: `supervisor-agent` (identical), `search_v2` and `reranking` tools
- **Updates**: `security-agent` with geographic compliance variations
- **Creates New**: `support-agent-business-tiers` for business tier targeting, MCP research tools
- **Skips Duplicates**: Won't recreate segments or configs that already exist

This approach lets you incrementally add capabilities without recreating existing infrastructure.

<div align="center">

![API Deployment Workflow](screenshots/api_deployment_workflow.png)
*LaunchDarkly API automation deploys complex configurations in seconds*

</div>

## Step 5: Verify in [LaunchDarkly UI](https://app.launchdarkly.com) (3 minutes)

Your configurations are now deployed! Let's verify everything was created correctly in the LaunchDarkly interface.

Check your LaunchDarkly project:

1. **Segments**: Navigate to Segments - you should see:
   - `eu-free`, `eu-paid`, `other-free`, `other-paid` (combined segments)

2. **AI Configs**: Check AI Configs - you should see:
   - `supervisor-agent`, `security-agent`, `support-agent-business-tiers`
   - Each with appropriate variations and targeting rules

3. **Preview**: Use the targeting preview to test different user contexts

<div align="center">

![LaunchDarkly Segments View](screenshots/launchdarkly_segments_view.png)
*Geographic and business tier segments in LaunchDarkly*

</div>

## Step 6: Test Segmentation with Script (3 minutes)

**Why Test Validation?** The included test script simulates real user scenarios across all segments, verifying that your targeting rules work correctly. It sends actual API requests to your system and confirms each user type gets the right model, tools, and behavior - giving you confidence before real users arrive.

Validate your segmentation with the test script:

```bash
uv run python test_tutorial_2.py
```

The script tests 4 user scenarios:
- EU Paid → Claude Sonnet + Full MCP tools
- EU Free → Claude Haiku + Basic tools
- Other Paid → GPT-4 + Full MCP tools  
- Other Free → GPT-4o Mini + Basic tools

All tests should pass, confirming your targeting works correctly.

## Step 7: Experience Segmentation in the Chat UI (3 minutes)

Now let's see your segmentation in action through the actual user interface that your customers will experience.

```bash
# Start your system (2 terminals)
uv run uvicorn api.main:app --reload --port 8001
API_PORT=8001 uv run streamlit run ui/chat_interface.py --server.port 8501
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