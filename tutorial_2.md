# Smart AI Agent Targeting with MCP Tools

## Overview

Here's what nobody tells you about multi-agentic systems: the hard part isn't building them but making them profitable. One misconfigured model serving enterprise features to free users can burn $20K in a weekend. Meanwhile, you're manually juggling dozens of requirements for different user tiers, regions, and privacy compliance and each one is a potential failure point.

*Part 2 of 3 of the series: **Chaos to Clarity: Defensible AI Systems That Deliver on Your Goals***

The solution? **LangGraph multi-agent workflows** controlled by **LaunchDarkly AI Config** targeting rules that intelligently route users: paid customers get premium tools and models, free users get cost-efficient alternatives, and EU users get Mistral for enhanced privacy. Use the **LaunchDarkly REST API** to set up a custom variant-targeting matrix in 2 minutes instead of spending hours setting it up manually.

## What You'll Build Today

In the next 18 minutes, you'll transform your basic multi-agent system with:

- **Business Tiers & MCP Integration**: Free users get internal keyword search, Paid users get premium models with RAG, external research tools and expanded tool call limits, all controlled by [LaunchDarkly AI Configs](https://launchdarkly.com/docs/home/ai-configs)
- **Geographic Targeting**: EU users automatically get Mistral and Claude models (enhanced privacy), other users get cost-optimized alternatives
- **Smart Configuration**: Set up complex targeting matrices with [LaunchDarkly segments](https://launchdarkly.com/docs/home/flags/segments) and [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)

## Prerequisites

✅ **[Part 1 completed](../agents-langgraph/agents-langgraph.mdx)** with exact naming:
- Project: `multi-agent-chatbot`
- AI Configs: `supervisor-agent`, `security-agent`, `support-agent`
- Tools: `search_v2`, `reranking`
- Variations: `supervisor-basic`, `pii-detector`, `rag-search-enhanced`

🔑 **Add to your `.env` file**:
```bash
LD_API_KEY=your-api-key        # Get from LaunchDarkly settings
MISTRAL_API_KEY=your-key       # Get from console.mistral.ai
```

### Getting Your LaunchDarkly API Key

The automation scripts in this tutorial use the LaunchDarkly REST API to programmatically create configurations. Here's how to get your API key:

To get your LaunchDarkly API key, start by navigating to Organization Settings by clicking the gear icon (⚙️) in the left sidebar of [your LaunchDarkly dashboard](https://app.launchdarkly.com/). Once there, access Authorization Settings by clicking **"Authorization"** in the settings menu. Next, create a new access token by clicking **"Create token"** in the "Access tokens" section.

<br />

<div align="center">

<Frame caption="Click 'Create token' in the Access tokens section">
![API Token Creation](../../../assets/images/tutorials/targeting-with-mcp/api_token.png)
</Frame>

</div>

When configuring your token, give it a descriptive name like "multi-agent-chatbot", select **"Writer"** as the role (required for creating configurations), use the default API version (latest), and leave "This is a service token" unchecked for now.

<br />

<div align="center">

<Frame caption="Configure your token with a descriptive name and Writer role">
![Name API Token](../../../assets/images/tutorials/targeting-with-mcp/name_api_token.png)
</Frame>

</div>

After configuring the settings, click **"Save token"** and immediately copy the token value. This is **IMPORTANT** because it's only shown once!

<br />

<div align="center">

<Frame caption="Copy the token value immediately - it's only shown once">
![Copy API Token](../../../assets/images/tutorials/targeting-with-mcp/copy_api_token.png)
</Frame>

</div>

Finally, add the token to your environment:
   ```bash
   # Add this line to your .env file
   LD_API_KEY=your-copied-api-key-here
   ```

**Security Note**: Keep your API key private and never commit it to version control. The token allows full access to your LaunchDarkly account.

## Step 1: Add External Research Tools (4 minutes)

Your agents need more than just your internal documents. **Model Context Protocol (MCP)** connects AI assistants to live external data and they agents become orchestrators of your digital infrastructure, tapping into databases, communication tools, development platforms, and any system that matters to your business. MCP tools run as separate servers that your agents call when needed.

> The [MCP Registry](https://registry.modelcontextprotocol.io) serves as a community-driven directory for discovering available MCP servers - like an app store for MCP tools. For this tutorial, we'll use manual installation since our specific academic research servers (ArXiv and Semantic Scholar) aren't yet available in the registry.

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

These tools integrate with your agents via LangGraph while LaunchDarkly controls which users get access to which tools.

## Step 2: Configure with API Automation (2 minutes)

Now we'll use programmatic API automation to configure the complete setup. The [LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api) lets you manage tools, segments, and [AI Configs](https://launchdarkly.com/docs/home/ai-configs) programmatically. Instead of manually creating dozens of variations in the UI, this **configuration automation** makes REST API calls to provision user segments, AI config variations, targeting rules, and tools. These are the same resources you could create manually through the LaunchDarkly dashboard. Your actual chat application continues running unchanged.

Configure your complete targeting matrix with one command:

```bash
cd bootstrap
uv run python create_configs.py
```

**What the script creates**:
- **3 new tools**: `search_v1` (basic search), `arxiv_search` and `semantic_scholar` (MCP research tools)
- **4 combined user segments** with [geographic and tier targeting rules](https://launchdarkly.com/docs/home/flags/segments)
- **Updated AI Configs**: `security-agent` with 2 new geographic variations
- **Complete [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)** that route users to appropriate variations
- **Intelligently reuses** existing resources: `supervisor-agent`, `search_v2`, and `reranking` tools from Part 1

## Step 3: See How Smart Segmentation Works (2 minutes)

Here's how it works: EU users get Mistral for security processing with Claude for support (privacy + compliance). Non-EU users get Claude for security and GPT for support (cost optimization). Free users get basic search tools, paid users get full research capabilities. All users get Claude for supervision and workflow orchestration.

This segmentation strategy optimizes costs while ensuring compliance: EU users get Mistral for security processing (enhanced privacy), non-EU users get GPT for support tasks (cost efficiency), with Claude handling supervision for all users.

## Step 4: Test Segmentation with Script (2 minutes)

The included test script simulates real user scenarios across all segments, verifying that your targeting rules work correctly. It sends actual API requests to your system and confirms each user type gets the right model, tools, and behavior - giving you confidence before real users arrive.

Validate your segmentation with the test script:

```bash
uv run api/test_tutorial_2.py
```

This confirms your targeting matrix is working correctly across all user segments!

## Step 5: Experience Segmentation in the Chat UI (3 minutes)

Now let's see your segmentation in action through the user interface.

```bash
# Start your system (2 terminals)
uv run uvicorn api.main:app --reload --port 8000
uv run streamlit run ui/chat_interface.py --server.port 8501
```

Open http://localhost:8501 and test different user types:

1. **User Dropdown**: Select different regions (eu, other) and plans (Free, Paid)
2. **Ask Questions**: Try "Search for machine learning papers" 
3. **Watch Workflow**: See which model and tools get used for each user type
4. **Verify Routing**: EU users get Mistral for security, Other users get GPT, Paid users get MCP tools

<br />

<div align="center">

<Frame caption="Select different user types to test segmentation in the chat interface">
![Chat Interface User Selection](../../../assets/images/tutorials/targeting-with-mcp/chat_interface.png)
</Frame>

</div>

## What's Next: Part 3 Preview

**In Part 3**, we'll prove what actually works using controlled A/B experiments:

### **Set up Easy Experiments**
- **Tool Implementation Test**: Compare search_v1 vs search_v2 on identical models to measure search quality impact
- **Model Efficiency Analysis**: Test models with the same full tool stack to measure tool-calling precision and cost

### **Real Metrics You'll Track**
- **User satisfaction**: thumbs up/down feedback
- **Tool call efficiency**: average number of tools used per successful query
- **Token cost analysis**: cost per query across different model configurations
- **Response latency**: performance impact of security and tool variations

Instead of guessing which configurations work better, you'll have data proving which tool implementations provide value, which models use tools more efficiently, and what security enhancements actually costs in performance.

## The Path Forward

You've built something powerful: a multi-agent system that adapts to users by design. More importantly, you've proven that sophisticated AI applications don't require repeated deployments; they require smart configuration.

This approach scales beyond tutorials. Whether you're serving 100 users or 100,000, the same targeting principles apply: segment intelligently, configure dynamically, and let data guide decisions instead of assumptions.


---
*Questions? Issues? Reach out at `aiproduct@launchdarkly.com` or open an issue in the [GitHub repo](https://github.com/launchdarkly-labs/devrel-agents-tutorial/issues).*