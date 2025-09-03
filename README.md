---
slug: /tutorials/multi-agent-ai-tutorial
title: "Building AI-Powered Multi-Agent Systems with LaunchDarkly"
description: Learn how to seamlessly integrate the best AI configurations with multi-agent workflows, real research capabilities, and traffic simulation
keywords: tutorial, AI, LaunchDarkly, multi-agent, MCP, RAG, FAISS, LangGraph, python
---
<p class="publishedDate"><em>Published January 2nd, 2025</em></p>
<div class="authorWrapper">
  <img
    src="../../../assets/images/authors/scarlett-attensil.png"
    alt="portrait of Scarlett Attensil."
    class="authorAvatar"
  ></img>
  <p class="authorName">by Scarlett Attensil</p>
</div>

## Overview

This tutorial walks you through building a multi-agent AI system that adapts to your users in real-time. You'll start with a working system, then customize it for your own use case by:

- **Replacing the knowledge base** with your own documents
- **Customizing agent instructions** for your domain  
- **Creating AI Config variations** that match your business tiers
- **Running experiments** to optimize performance

By the end, you'll have three specialized agents (supervisor, security checker, and research assistant) that work with YOUR content and YOUR business logic.


## Why Dynamic Configuration Matters

Here's a painfully familiar scenario: You built a system using GPT-4, but now you're curious if Claude 3.5 might be cheaper without reducing user satisfaction (i.e. your AWS bill is getting scary). In traditional architectures, this "simple" test requires:

- Development time to swap model integrations (there goes your weekend)
- Testing across multiple environments
- Coordinated deployment and rollback planning
- Potential downtime during the switch (and angry users)

The result? You avoid experimenting with new models, missing out on potential cost savings and performance improvements. Worse, your AI decisions get made based on vibes rather than data.

This tutorial demonstrates a different approach: **runtime configuration** that brings order to the chaos of AI model selection. Instead of endless debates about which model is "better," you get data-driven answers. You can justify every AI decision with real metrics while getting model switching, subscription-based tool access, and geographic customization (all controlled through LaunchDarkly AI Configs).

## What We're Building

A **multi-agent AI system** with three specialized agents that demonstrates dynamic configuration in action. The key architectural difference is **external configuration control** - instead of hardcoding agent behavior, every decision flows through LaunchDarkly AI Configs:

```
User Query → Supervisor Agent → Security Agent (PII Detection)
                ↓               ↓
            Support Agent → Final Response
         (Research & RAG)
                ↑
     LaunchDarkly AI Configs
```

**The advantage**: Configuration changes happen quickly. Model selection, tool access, and agent instructions are all controlled through the LaunchDarkly dashboard.

## Technology Stack Overview

This system integrates five key technologies that work together to create a flexible, production-ready AI application:

### **1. Dynamic AI Configuration (LaunchDarkly AI Configs)**
Runtime control over model selection, tool access, and agent instructions.

### **2. Retrieval-Augmented Generation** 
Vector search with FAISS indexing, BM25 reranking for improved relevance, and semantic document chunking.

### **3. Model Context Protocol Integration**
Live data access through academic databases (ArXiv, Semantic Scholar) for real-time research capabilities.

### **4. Multi-Agent LangGraph Orchestration**  
Workflow management with state persistence and conditional routing between specialized agents.

## Prerequisites

In order to complete this tutorial, you must have the following prerequisites:

- Python 3.9+ with `uv` package manager
- A LaunchDarkly account with AI Configs enabled ([sign up for a free one here](https://app.launchdarkly.com/signup))
- API keys for Anthropic Claude and/or OpenAI GPT models
- Basic familiarity with FastAPI and LangChain concepts



## Detailed Technology Implementation

### **🔍 RAG (Retrieval-Augmented Generation) Implementation**

This system implements RAG with several key components:

**Core Features**:
- **FAISS vector indexing** for efficient semantic document retrieval
- **BM25 reranking** as a separate tool to improve search result relevance
- **Two-stage approach** where agents can use vector search first, then optionally rerank results with BM25
- **Optimized chunking** strategies for better document processing

```python
# tools_impl/search_v2.py - Advanced RAG implementation
@lru_cache(maxsize=128)
def _cached_search(query: str, top_k: int, min_score: float) -> List[Tuple[str, float, Dict]]:
    vs = _get_vector_store()
    # Ask store for extra results and then threshold+trim
    raw = vs.search(query, top_k=min(top_k * 2, 50))
    
    # Filter by minimum similarity score
    filtered = [(text, score, meta) for text, score, meta in raw if score >= min_score]
    return filtered[:top_k]

class SearchToolV2(BaseTool):
    name: str = "search_v2"
    description: str = (
        "Advanced vector semantic search over enterprise AI/ML docs. "
        "Returns human summary and JSON payload with items=[{text, score, metadata}]."
    )
    
    def _run(self, query: str, top_k: int = 3, min_score: float = 0.20) -> str:
        results = _cached_search(query, top_k, min_score)
        # Return formatted results with similarity scores
        return f"Found {len(results)} relevant documents..."
```

### **🛡️ PII Detection & Security Agent**

The security agent demonstrates how you can use model-native capabilities for privacy protection.

**What it actually does**:
- **Model-native detection** using Claude/GPT's built-in PII recognition capabilities
- **Configurable instructions** that can be updated through LaunchDarkly for different compliance requirements
- **Geographic variation ready** - you could easily add targeting rules to serve different security models based on user location

```python
# agents/security_agent.py - PII detection implementation
def create_security_agent(agent_config: AgentConfig, config_manager: ConfigManager):
    """Create security agent using LDAI SDK pattern"""
    
    # Create model from LaunchDarkly AI Config
    model_name = agent_config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=agent_config.model, temperature=agent_config.temperature)
    else:
        model = ChatAnthropic(model=agent_config.model, temperature=agent_config.temperature)
    
    def security_node(state: AgentState):
        """Security analysis with LaunchDarkly tracking"""
        system_prompt = f"""
        {agent_config.instructions}
        
        Analyze for PII and compliance:
        - Personal identifiers (emails, phone numbers)
        - Sensitive data requiring protection
        - Regional compliance (GDPR, etc.)
        """
        
        # Track metrics through LaunchDarkly AI Config tracker
        response = config_manager.track_metrics(
            agent_config.tracker,
            lambda: model.invoke([SystemMessage(content=system_prompt),
                                HumanMessage(content=state["user_input"])])
        )
        
        return {"response": response.content}
```

### **🔬 MCP (Model Context Protocol) Integration**

The Model Context Protocol enables AI agents to access live external data sources, extending beyond static knowledge bases.

**Key capabilities**:
- **Real-time research** access to ArXiv and Semantic Scholar databases
- **Configurable access** through LaunchDarkly targeting (you could limit expensive tools to enterprise users)
- **Tool composition** that extends agent capabilities beyond their training data
- **Production reliability** with proper error handling and fallback mechanisms

```python
# tools_impl/mcp_research_tools.py - MCP server integration
server_configs = {
    "arxiv": {
        "command": "/Users/ld_scarlett/.local/bin/arxiv-mcp-server",
        "args": ["--storage-path", "/tmp/arxiv-papers"]
    },
    "semanticscholar": {
        "command": "python", 
        "args": ["/path/to/semanticscholar-MCP-Server/main.py"]
    }
}
```

### **🕸️ LangGraph Orchestration: Beyond the Hype**

Most teams building "multi-agent systems" are just chaining prompts together and calling it architecture. Real multi-agent systems need **proper state management**.

**What multi-agent actually looks like**:
- **Conditional routing** that makes intelligent decisions (not just a glorified if/else statement)
- **State persistence** across agent handoffs (because agents with amnesia are useless)
- **Error recovery** because agents fail more often than your New Year's resolutions
- **Parallel execution** when agents can work independently

```python
# agents/supervisor_agent.py - LangGraph workflow implementation
def create_supervisor_agent(supervisor_config, support_config, security_config, config_manager):
    """Create supervisor agent using LDAI SDK pattern"""
    
    # Build supervisor workflow
    workflow = StateGraph(SupervisorState)
    
    # Add nodes for each agent
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("security_agent", security_node)
    workflow.add_node("support_agent", support_node)
    workflow.add_node("revise", revise_node)
    workflow.add_node("format_final", format_final)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "security_agent": "security_agent",
            "support_agent": "support_agent", 
            "revise": "revise",
            "complete": "format_final"
        }
    )
    
    # After each agent, return to supervisor
    workflow.add_edge("security_agent", "supervisor")
    workflow.add_edge("support_agent", "supervisor")
    workflow.add_edge("revise", "supervisor")
    
    # Final node
    workflow.set_finish_point("format_final")
    
    return workflow.compile()
```

### **⚙️ LaunchDarkly AI Configs: The Game Changer**

Here's the key insight: instead of hardcoding configurations in your code, you can manage them as a service through LaunchDarkly.

**Why this matters more than arguing about which model is "better"**:
- **Zero-downtime model switching** (swap models without deployments)
- **Subscription-based access** (enterprise users get research tools, free users get basic search)
- **Geographic compliance** happens automatically
- **Real-time A/B testing** with statistical significance that would make a data scientist shed a tear of joy

```python
# config_manager.py - LaunchDarkly AI Config integration
config, tracker = self.ai_client.config(config_key, ld_user_context, fallback)

# Automatic metrics tracking for all AI operations
response = config_manager.track_metrics(
    config.tracker,
    lambda: model_with_tools.invoke(state["messages"])
)
```

## Why This Architecture Works

This system puts configuration first. LaunchDarkly AI Configs control everything: model choice, tool access, and agent behavior, before any agent runs.

**The flow that actually scales**:
1. **LaunchDarkly AI Configs** decide everything before any agent runs (model choice, tool access, compliance requirements)
2. **LangGraph Supervisor** routes based on configuration and workflow state (not hardcoded logic)  
3. **Security Agent** runs first with compliance rules determined by user geography
4. **Support Agent** gets tools and instructions tailored to subscription tier
5. **RAG + MCP** provide the intelligence, but configuration controls the costs

```python
# The complete flow in action:
LaunchDarkly Config → LangGraph Supervisor → Security Agent (GDPR-aware) 
    → Support Agent → RAG Search + MCP Research → Final Response
    ↑ (30-second config changes)                           ↓ (real-time metrics)
```

**Result**: Product requirements become configuration changes, not engineering tickets.

## Building It: The Implementation That Surprised Me

After building this system, I realized most AI architectures are way more complicated than they need to be. The implementation is straightforward once you stop hardcoding everything.

What you'll build in the next 20 minutes:
- A multi-agent system with dynamic model switching through configuration
- Geographic compliance that happens automatically
- Cost controls that prevent those heart-attack-inducing API bills
- Easy experimentation capabilities for all varieties of models, prompts, and tool combinations

## Setting Up the API

```python
# api/main.py
from fastapi import FastAPI
from .models import ChatRequest, ChatResponse
from .services.agent_service import AgentService

app = FastAPI()
agent_service = AgentService()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"🌐 API: Received chat request from user {request.user_id}")
    
    result = await agent_service.process_message(
        user_id=request.user_id,
        message=request.message,
        user_context=request.user_context  # 🎯 This drives LaunchDarkly targeting!
    )
    
    return result
```

### Configuration Magic

```python
# config_manager.py
from ldai.client import LDAIClient, AIConfig, ModelConfig

class FixedConfigManager:
    def __init__(self):
        self.sdk_key = os.getenv('LD_SDK_KEY')
        self._initialize_launchdarkly_client()
        self._initialize_ai_client()
    
    async def get_config(self, user_id: str, config_key: str, user_context: dict = None):
        """The magic happens here - get AI config from LaunchDarkly"""
        
        # Build targeting context
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])  # 🇪🇺 EU gets Claude!
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])        # 💎 Enterprise gets MCP tools!
        
        ld_user_context = context_builder.build()
        
        # Get AI Config with metrics tracker
        config, tracker = self.ai_client.config(config_key, ld_user_context, fallback)
        
        # Parse into our AgentConfig format
        agent_config = self._parse_ai_config_object(config, config_key)
        agent_config.tracker = tracker  # 📊 Built-in metrics tracking!
        
        return agent_config
```

### Multi-Agent Orchestration

```python
# agents/supervisor_agent.py
def create_supervisor_agent(supervisor_config, support_config, security_config, config_manager):
    """This is where the magic happens - LaunchDarkly controls everything!"""
    
    def supervisor_node(state):
        # 🎯 LaunchDarkly AI Config controls the routing logic
        decision_start = config_manager.track_metrics(
            supervisor_config.tracker,  # 📊 Built-in metrics!
            lambda: "supervisor_decision_start"
        )
        
        # Smart routing based on workflow stage
        if workflow_stage == "initial_security" and not security_cleared:
            next_agent = "security_agent"
        elif workflow_stage == "research" and not support_response:
            next_agent = "support_agent"
        else:
            # Use AI model for complex decisions
            response = config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: supervisor_model.invoke([prompt])  # 🤖 Model choice from LaunchDarkly!
            )
            next_agent = response.content.strip().lower()
        
        return {"current_agent": next_agent}
```

**The magic happens here**: No hardcoded model choices. Just pure, dynamic intelligence.

## The 3-Step Implementation (Faster Than You Think)

### Step 1: LaunchDarkly AI Configs (The Control Center)

AI Configs are **runtime intelligence controllers**, basically the puppet master for your AI agents.

Here's what you're actually building:
1. **supervisor-agent**: The orchestra conductor that routes between security and support
2. **security-agent**: Your privacy bouncer for PII detection 
3. **support-agent**: 5 different flavors from "basic search peasant" to "$2000/month research wizard" depending on your tier

The setup takes seriously just 2 minutes in the LaunchDarkly dashboard:
- Navigate to AI Configs
- Create three AI Configs with the names above
- Configure variations and targeting rules

<Callout intent="info">
Screenshots in this tutorial show placeholder images. In your actual LaunchDarkly dashboard, you'll see the real configuration interface.
</Callout>

<Frame caption="Creating AI Configs in the LaunchDarkly dashboard">
  ![LaunchDarkly AI Configs Setup](screenshots/ai-configs-setup.png)
</Frame>

### 1. **Supervisor Agent** - The Orchestra Conductor

**Role**: Routes between security and support agents based on LaunchDarkly configuration

```python
# agents/supervisor_agent.py
def security_node(state):
    """Route to security agent with LDAI metrics tracking"""
    print(f"🎯 SUPERVISOR: Orchestrating security agent execution")
    
    # Track supervisor orchestration start
    config_manager.track_metrics(
        supervisor_config.tracker,
        lambda: "supervisor_orchestrating_security_start"
    )
    
    # Execute security agent
    result = security_agent.invoke(security_input)
    
    # Track successful completion
    config_manager.track_metrics(
        supervisor_config.tracker,
        lambda: "supervisor_orchestrating_security_success"
    )
    
    return {
        "messages": [AIMessage(content=result["response"])],
        "workflow_stage": "research",
        "security_cleared": True
    }
```

### 2. **Security Agent** - The Privacy Guardian

**Role**: PII detection and compliance using native model capabilities

```python
# agents/security_agent.py
def create_security_agent(config, config_manager):
    """Security agent controlled by LaunchDarkly AI Config"""
    
    # Model choice controlled by LaunchDarkly
    if "gpt" in config.model.lower():
        model = ChatOpenAI(model=config.model, temperature=config.temperature)
    else:
        model = ChatAnthropic(model=config.model, temperature=config.temperature)
    
    def security_check(state):
        # Instructions controlled by LaunchDarkly AI Config
        system_prompt = f"""
        {config.instructions}
        
        Analyze the following text for PII and privacy concerns:
        - Personal information (names, emails, phone numbers)
        - Sensitive data that should be flagged
        - Compliance issues
        """
        
        # Track with LaunchDarkly AI metrics
        response = config_manager.track_metrics(
            config.tracker,
            lambda: model.invoke([SystemMessage(content=system_prompt), 
                                HumanMessage(content=state["user_input"])])
        )
        
        return {"response": response.content}
```

### 3. **Support Agent** - The Research Powerhouse

**Role**: RAG + MCP research capabilities, all controlled by LaunchDarkly

```python
# agents/support_agent.py
def create_support_agent(config, config_manager):
    """Support agent with LaunchDarkly-controlled tool access"""
    
    # Tools controlled by LaunchDarkly AI Config!
    available_tools = []
    
    if "search_v1" in config.allowed_tools:
        available_tools.append(SearchToolV1())
    
    if "search_v2" in config.allowed_tools:
        available_tools.append(SearchToolV2())
    
    if "reranking" in config.allowed_tools:
        available_tools.append(RerankingTool())
    
    # 🔬 MCP Research Tools (expensive, only for enterprise!)
    if "arxiv_search" in config.allowed_tools:
        mcp_tools = await get_research_tools()
        available_tools.extend(mcp_tools["arxiv"])
    
    if "semantic_scholar" in config.allowed_tools:
        mcp_tools = await get_research_tools()
        available_tools.extend(mcp_tools["semantic_scholar"])
    
    # Bind tools to model
    model_with_tools = model.bind_tools(available_tools)
    
    def agent_step(state):
        # Track tool usage with LaunchDarkly AI metrics
        response = config_manager.track_metrics(
            config.tracker,
            lambda: model_with_tools.invoke(state["messages"])
        )
        
        return {"response": response.content, "tool_calls": [tool.name for tool in response.tool_calls]}
```

## The Configurations

<Frame caption="AI Config variations and targeting rules in LaunchDarkly dashboard">
  ![LaunchDarkly AI Config Variations](screenshots/ai-config-variations.png)
</Frame>



### **supervisor-agent** Configuration
```json
{
  "model": {
    "name": "claude-3-7-sonnet-latest"
  },
  "instructions": "You are a helpful AI assistant that can search documentation.",
  "temperature": 0.0,
  "tools": ["search_v2", "reranking", "semantic_scholar", "arxiv_search"],
  "variationKey": "main"
}
```

### **support-agent** Configuration with 5 Variations

This is where it gets spicy: Most AI systems have one configuration and call it a day. This system has **5 different variations** that range from "basic chatbot" to "I have a research budget that makes academics weep with envy."

**Variation 1: `no-tools`** (The baseline)
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in AI/ML technical support. Provide clear, accurate, and detailed explanations about AI/ML concepts, algorithms, and techniques. Use available tools to search through technical documentation when needed.",
  "max_cost": 1,
  "max_tool_calls": 8,
  "workflow_type": "conditiona...",
  "tools": [],
  "variationKey": "no-tools"
}
```

**Variation 2: `search-only-v1`** (Basic search unlocked)
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in AI/ML technical support.\nProvide clear, accurate, and detailed explanations about AI/ML concepts, algorithms, and techniques.\n\n## Tool Usage Guidelines\n\n### Duplicate Prevention (CRITICAL)\n- Maximum 8 tool calls total - use them strategically\n- NEVER make identical tool calls with the same exact query\n- Each tool call must have a unique search query or parameters\n- If previous queries are shown below, do not repeat them\n- Use varied search terms to explore different facets of the topic\n\n### Research Strategy\n- Use available tools strategically to gather comprehensive information\n- Be strategic - use different queries to explore different aspects\n- Focus on quality over quantity of searches\n\n### Completion Criteria\n- Use as many unique searches as needed for comprehensive coverage\n- Include specific details, examples, and well-structured explanations\n- Aim for thorough responses that fully address the user's needs\n- Stop when you have sufficient diverse information to provide complete answer",
  "max_cost": 1,
  "max_tool_calls": 8,
  "tools": ["search_v1"],
  "variationKey": "search-only-v1"
}
```

**Variation 3: `search-only-v2`** (Advanced search with semantic understanding)
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in AI/ML technical support.\nProvide clear, accurate, and detailed explanations about AI/ML concepts, algorithms, and techniques.\n\n## Tool Usage Guidelines\n\n### Duplicate Prevention (CRITICAL)\n- Maximum 8 tool calls total - use them strategically\n- NEVER make identical tool calls with the same exact query\n- Each tool call must have a unique search query or parameters\n- If previous queries are shown below, do not repeat them\n- Use varied search terms to explore different facets of the topic\n\n### Research Strategy\n- Use available tools strategically to gather comprehensive information\n- Be strategic - use different queries to explore different aspects\n- Focus on quality over quantity of searches\n\n### Completion Criteria\n- Use as many unique searches as needed for comprehensive coverage\n- Include specific details, examples, and well-structured explanations\n- Aim for thorough responses that fully address the user's needs\n- Stop when you have sufficient diverse information to provide complete answer",
  "max_cost": 1,
  "max_tool_calls": 8,
  "tools": ["search_v2"],
  "variationKey": "search-only-v2"
}
```

**Variation 4: `full-research-claude`** (The enterprise powerhouse - Claude edition)
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a helpful AI assistant specialized in AI/ML technical support.\nProvide clear, accurate, and detailed explanations about AI/ML concepts, algorithms, and techniques.\n\n## Tool Usage Guidelines\n\n### Duplicate Prevention (CRITICAL)\n- Maximum 8 tool calls total - use them strategically\n- NEVER make identical tool calls with the same exact query\n- Each tool call must have a unique search query or parameters\n- If previous queries are shown below, do not repeat them\n- Use varied search terms to explore different facets of the topic\n\n### Research Strategy\n- Use available tools strategically to gather comprehensive information\n- Be strategic - use different queries to explore different aspects\n- Focus on quality over quantity of searches\n\n### Completion Criteria\n- Use as many unique searches as needed for comprehensive coverage\n- Include specific details, examples, and well-structured explanations\n- Aim for thorough responses that fully address the user's needs\n- Stop when you have sufficient diverse information to provide complete answer",
  "max_cost": 1,
  "max_tool_calls": 8,
  "tools": ["semantic_scholar", "search_v2", "reranking", "arxiv_search"],
  "variationKey": "full-research-claude"
}
```

**Variation 5: `full-research-openai`** (Same tools, different model - perfect for A/B testing)
```json
{
  "model": {"name": "chatgpt-4o-latest"},
  "instructions": "You are a helpful AI assistant specialized in AI/ML technical support.\nProvide clear, accurate, and detailed explanations about AI/ML concepts, algorithms, and techniques.\n\n## Tool Usage Guidelines\n\n### Duplicate Prevention (CRITICAL)\n- Maximum 8 tool calls total - use them strategically\n- NEVER make identical tool calls with the same exact query\n- Each tool call must have a unique search query or parameters\n- If previous queries are shown below, do not repeat them\n- Use varied search terms to explore different facets of the topic\n\n### Research Strategy\n- Use available tools strategically to gather comprehensive information\n- Be strategic - use different queries to explore different aspects\n- Focus on quality over quantity of searches\n\n### Completion Criteria\n- Use as many unique searches as needed for comprehensive coverage\n- Include specific details, examples, and well-structured explanations\n- Aim for thorough responses that fully address the user's needs\n- Stop when you have sufficient diverse information to provide complete answer",
  "max_cost": 1,
  "max_tool_calls": 8,
  "tools": ["semantic_scholar", "search_v2", "reranking", "arxiv_search"],
  "variationKey": "full-research-openai"
}
```

### **security-agent** Configuration

**Current Implementation**: Single variation for PII detection

```json
{
  "model": {
    "name": "claude-3-7-sonnet-latest"
  },
  "instructions": "You are a helpful AI assistant that can search documentation.",
  "temperature": 0.0,
  "tools": ["search_v2", "reranking", "semantic_scholar", "arxiv_search"],
  "variationKey": "pii-and-compliance"
}
```

**Note**: True regional adaptation would require multiple variations. For example:

**Hypothetical EU Variation** (`eu-privacy-strict`):
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a privacy-focused security agent. Apply strict PII detection including: names, emails, phone numbers, addresses, IP addresses, device IDs. Flag any personal identifiers for removal. Err on the side of caution for data protection.",
  "variationKey": "eu-privacy-strict"
}
```

**Hypothetical US Variation** (`us-standard-privacy`):
```json
{
  "model": {"name": "claude-3-7-sonnet-latest"},
  "instructions": "You are a security agent focused on detecting sensitive PII including: SSNs, credit card numbers, banking information, medical records. Apply standard privacy measures while maintaining system functionality.",
  "variationKey": "us-standard-privacy"
}
```

The current system uses a single security configuration, but the architecture supports multiple variations through LaunchDarkly targeting rules.

<Frame caption="Geographic and subscription-based targeting rules in LaunchDarkly">
  ![LaunchDarkly Targeting Rules](screenshots/targeting-rules.png)
</Frame>

## Customizing Your AI Configs

Now that you understand the structure, let's make this system work for YOUR use case:

### **Step 1: Customize Agent Instructions**

In your LaunchDarkly dashboard:

1. **Navigate to your `support-agent` AI Config**
2. **Edit the instructions** to match your domain:

```json
{
  "instructions": "You are a helpful assistant specialized in [YOUR DOMAIN]. Provide clear, accurate explanations about [YOUR TOPICS]. Use available tools to search through [YOUR COMPANY] documentation when needed.",
  "tools": ["search_v2", "reranking"]
}
```

**Examples for different domains**:
- **E-commerce**: "You are a customer support specialist for [COMPANY]. Help users with orders, returns, product questions, and account issues."
- **Healthcare**: "You are a medical information assistant. Provide accurate information about treatments, procedures, and health conditions based on our medical knowledge base."
- **Legal**: "You are a legal research assistant. Help users find relevant case law, statutes, and legal precedents from our legal database."

### **Step 2: Create Your Own Variations**

Instead of using our AI/ML focused variations, create ones for your business:

**Example: Customer Support Tiers**
```json
// Free tier - basic search only
{
  "model": {"name": "claude-3-haiku-20240307"},
  "instructions": "You are a basic customer support assistant. Answer common questions using our FAQ database.",
  "tools": ["search_v1"],
  "max_cost": 0.50
}

// Premium tier - full capabilities  
{
  "model": {"name": "claude-3-5-sonnet-20241022"},
  "instructions": "You are an expert customer support specialist with access to our full knowledge base and external resources.",
  "tools": ["search_v2", "reranking", "external_api"],
  "max_cost": 2.0
}
```

### **Step 3: Test Your Customizations**

<CodeBlocks>
<CodeBlock>
```bash
# Test with questions specific to your domain
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Your domain-specific question here",
    "user_context": {"plan": "premium", "country": "US"}
  }'
```
</CodeBlock>
</CodeBlocks>

**What These 5 Variations Demonstrate**:

These configurations show how dynamic AI systems can support different business models and use cases:

- **Tiered Access**: From basic responses (`no-tools`) to advanced research capabilities (`full-research-*`)
- **Model Comparison**: Direct A/B testing between Claude and OpenAI with identical tool configurations
- **Cost Management**: Built-in `max_cost` limits and strategic tool usage to control API expenses
- **Progressive Enhancement**: Scaling from simple search to comprehensive research workflows
- **Efficiency Optimization**: Instructions designed to prevent redundant API calls and improve response quality

**Key insight**: Different user tiers can be served through configuration rather than separate codebases, enabling rapid iteration and testing.

### Step 2: Implementing MCP Research Integration

The Model Context Protocol (MCP) integration provides agents with access to live academic databases:

```python
# tools_impl/mcp_research_tools.py
class MCPResearchTools:
    """Real MCP integration with ArXiv and Semantic Scholar"""
    
    async def initialize(self):
        """Connect to MCP servers"""
        server_configs = {
            # ArXiv MCP Server - Academic papers
            "arxiv": {
                "command": "/Users/ld_scarlett/.local/bin/arxiv-mcp-server", 
                "args": ["--storage-path", "/tmp/arxiv-papers"]
            },
            # Semantic Scholar - Citation database
            "semanticscholar": {
                "command": "python",
                "args": ["/path/to/semanticscholar-MCP-Server/main.py"]
            }
        }
        
        # Initialize MCP client
        server_connections = []
        for name, config in server_configs.items():
            print(f"🔗 MCP: Connecting to {name} server...")
            connection = StdioConnection(
                command=config["command"],
                args=config.get("args", [])
            )
            server_connections.append((name, connection))
        
        self.client = MultiServerMCPClient()
        await self.client.connect(server_connections)
        
        # Load tools from all servers
        self.tools = await load_mcp_tools(self.client)
        print(f"✅ MCP: Loaded {len(self.tools)} research tools")

async def get_research_tools():
    """Get MCP research tools - expensive, so LaunchDarkly controls access!"""
    global _MCP_SINGLETON
    
    if _MCP_SINGLETON is None:
        _MCP_SINGLETON = MCPResearchTools()
        await _MCP_SINGLETON.initialize()
    
    return {
        "arxiv": [tool for tool in _MCP_SINGLETON.tools if "arxiv" in tool.name.lower()],
        "semantic_scholar": [tool for tool in _MCP_SINGLETON.tools if "semantic" in tool.name.lower()]
    }
```

LaunchDarkly controls access to these expensive MCP tools - only enterprise users with the `research-enhanced` variation get access, while free users are limited to basic search functionality.

### Step 3: Creating the Agent Implementation

Now implement the three specialized agents:

#### Supervisor Agent - Workflow Orchestration

The supervisor agent routes requests between security and support agents:

```python
#!/usr/bin/env python3
# tools/traffic_generator.py
"""
Dead simple traffic generator for LaunchDarkly experiment data
"""

def send_chat_request(user, query_data):
    """Send a single chat request"""
    request_data = {
        "user_id": user["id"],
        "message": query_data["query"],
        "user_context": {
            "country": user["country"],  # 🇪🇺 EU users get Claude
            "region": user["region"], 
            "plan": user["plan"]         # 💎 Enterprise gets MCP tools
        }
    }
    
    print(f"🤖 SENDING: {user['id']} from {user['country']} asks: '{query_data['query'][:50]}...'")
    
    response = requests.post(f"{API_BASE_URL}/chat", json=request_data, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ SUCCESS: Got {len(result['response'])} chars, used {len(result['tool_calls'])} tools")
        return result

def simulate_feedback(response_data, query_data):
    """Simulate realistic user feedback"""
    thumbs_up_score = 0
    
    response_text = response_data["response"].lower()
    response_length = len(response_data["response"])
    tools_used = response_data["tool_calls"]
    
    # Simple rules anyone can modify:
    if response_length > 200:
        thumbs_up_score += 30  # Good length
    
    if len(tools_used) > 0:
        thumbs_up_score += 25  # Used research tools
    
    if "arxiv" in str(tools_used):
        thumbs_up_score += 35  # Academic research bonus
    
    if any(word in response_text for word in ["detailed", "comprehensive", "research"]):
        thumbs_up_score += 20  # Quality indicators
    
    # Random variation
    thumbs_up_score += random.randint(-15, 15)
    
    return "positive" if thumbs_up_score > 40 else "negative"
```

#### Security Agent - PII Detection

Implements privacy compliance and PII detection:

```python
# agents/security_agent.py
def create_security_agent(config, config_manager):
    # Model selection based on LaunchDarkly configuration
    model = ChatAnthropic(model=config.model, temperature=config.temperature)
    
    def security_node(state):
        system_prompt = f"""{config.instructions}
        
        Analyze for PII and compliance issues:
        - Personal identifiers
        - Sensitive data
        - Regional compliance requirements
        """
        
        response = config_manager.track_metrics(
            config.tracker,
            lambda: model.invoke([SystemMessage(content=system_prompt)])
        )
        
        return {"response": response.content, "security_cleared": True}
```

#### Support Agent - Research and RAG

Handles user queries with configurable tool access:

```python
# agents/support_agent.py  
def create_support_agent(config, config_manager):
    # Tools loaded based on LaunchDarkly configuration
    available_tools = []
    
    if "search_v1" in config.allowed_tools:
        available_tools.append(SearchToolV1())
    if "arxiv_search" in config.allowed_tools:
        available_tools.extend(get_research_tools()["arxiv"])
        
    model_with_tools = model.bind_tools(available_tools)
    
    def support_node(state):
        response = config_manager.track_metrics(
            config.tracker,
            lambda: model_with_tools.invoke(state["messages"])
        )
        
        return {
            "response": response.content,
            "tool_calls": [tool.name for tool in response.tool_calls]
        }
```

### Step 4: Traffic Generation and Testing

Create realistic test data using the included traffic generator. The `data/fake_users.json` includes geographic and plan targeting:

```json
{
  "users": [
    {
      "id": "user_us_free_001",
      "country": "US",
      "region": "north_america",
      "plan": "free",
      "description": "US free tier user"
    },
    {
      "id": "user_eu_enterprise_001",
      "country": "DE",
      "region": "europe", 
      "plan": "enterprise",
      "description": "German enterprise customer"
    },
    {
      "id": "user_asia_pro_001",
      "country": "SG",
      "region": "asia_pacific",
      "plan": "pro", 
      "description": "Singapore professional user"
    }
  ],
  "notes": {
    "targeting_strategy": {
      "free_tier": "Get basic tools only to control costs",
      "enterprise": "Get full research tools including expensive MCP",
      "eu_users": "Always get Claude for privacy compliance",
      "us_users": "Mixed variations for A/B testing"
    }
  }
}
```

## Running the Complete System

To run the system locally:

### 1. Initial Setup

<CodeBlocks>
<CodeBlock>
```bash
# Clone and install
git clone <your-repo>
cd agents-demo
uv sync
cp .env.example .env  # Add your LaunchDarkly and AI API keys
```
</CodeBlock>
</CodeBlocks>

### 2. Install MCP Research Tools

<CodeBlocks>
<CodeBlock>
```bash
# ArXiv MCP Server
uv tool install arxiv-mcp-server

# Semantic Scholar MCP Server  
git clone https://github.com/JackKuo666/semanticscholar-MCP-Server.git
uv add requests beautifulsoup4 mcp semanticscholar
```
</CodeBlock>
</CodeBlocks>

### 3. Customize Your Knowledge Base

Before running the system, let's make it yours by adding your own documents:

<CodeBlocks>
<CodeBlock>
```bash
# Replace the sample PDF with your own documents
rm kb/SuttonBartoIPRLBook2ndEd.pdf

# Add your own PDFs (company docs, research papers, etc.)
cp /path/to/your-document.pdf kb/
cp /path/to/another-document.pdf kb/

# Initialize embeddings with your documents
uv run initialize_embeddings.py --force
```
</CodeBlock>
</CodeBlocks>

**What this does**: Creates a vector database from YOUR documents so the RAG system searches through your content instead of generic AI/ML papers.

### 4. Start the Application

<CodeBlocks>
<CodeBlock>
```bash
# Terminal 1: Backend API
uv run uvicorn api.main:app --reload --port 8001

# Terminal 2: Chat UI
uv run streamlit run ui/chat_interface.py
```
</CodeBlock>
</CodeBlocks>

### 5. Generate Test Traffic

<CodeBlocks>
<CodeBlock>
```bash
# Generate realistic experiment data
python tools/traffic_generator.py --queries 50 --delay 2

# Quick test
python tools/traffic_generator.py --queries 10 --delay 2 --verbose

# Fake traffic
python tools/traffic_generator.py --queries 500 --delay 0.5
```
</CodeBlock>
</CodeBlocks>

## Results and Metrics

Once you run the system, you'll see experiment data flowing to your LaunchDarkly dashboard:

- **Geographic Targeting**: EU users receive Claude models for compliance
- **Plan-Based Features**: Enterprise users get research tools
- **Performance Metrics**: Response times, tool usage, and satisfaction rates
- **Cost Control**: Feature access controlled by subscription tier

<Frame caption="Real-time AI metrics and experiment results in LaunchDarkly">
  ![LaunchDarkly Metrics Dashboard](screenshots/metrics-dashboard.png)
</Frame>

LaunchDarkly AI Configs provide automatic metrics tracking including:
- **Duration**: Response generation time
- **Token usage**: Input/output token consumption 
- **Time to first token**: Latency measurements
- **Success/error rates**: Generation reliability
- **Custom satisfaction metrics**: User feedback integration



## Experimentation: Finding the Best AI Configuration

LaunchDarkly AI Configs enable the kind of experimentation that makes data scientists do happy dances. You can A/B test different aspects to find what works best and finally settle those "my model is better" arguments with actual data.

**Why this matters**: AI development often feels like chaos (too many models, too many variables, too many opinions). LaunchDarkly brings order to this chaos by letting you test everything systematically and justify your AI model selections with real metrics instead of gut feelings.

### **Experiment 1: RAG Enhancement Impact**

**Hypothesis**: Adding RAG search and reranking will increase user satisfaction by 15% while keeping token usage increase under 25%.

**Setup**:
- **Control (A)**: Basic search only (`["search_v1"]`)
- **Treatment (B)**: Enhanced RAG (`["search_v2", "reranking"]`)

**Success Metrics**:
- Primary: User satisfaction score improvement ≥ 15%
- Secondary: Token usage increase ≤ 25%
- Guardrail: Response time increase ≤ 2 seconds

```json
{
  "experiment_name": "rag-enhancement-test",
  "variations": {
    "control": {
      "model": "claude-3-5-sonnet-20241022",
      "tools": ["search_v1"],
      "traffic_allocation": 50
    },
    "treatment": {
      "model": "claude-3-5-sonnet-20241022", 
      "tools": ["search_v2", "reranking"],
      "traffic_allocation": 50
    }
  }
}
```

### **Experiment 2: Model Provider Tool Call Efficiency**

**Hypothesis**: Claude demonstrates superior tool usage efficiency compared to OpenAI, achieving 20% lower token consumption and 10% higher satisfaction scores.

**Setup**:
- **Control (A)**: OpenAI GPT-4o with full toolset
- **Treatment (B)**: Claude Sonnet with identical toolset

**Success Metrics**:
- Primary: Token usage reduction ≥ 20%
- Secondary: User satisfaction improvement ≥ 10%

```json
{
  "experiment_name": "model-efficiency-test",
  "variations": {
    "openai": {
      "model": "gpt-4o",
      "tools": ["search_v2", "reranking", "arxiv_search"],
      "traffic_allocation": 50
    },
    "claude": {
      "model": "claude-3-5-sonnet-20241022",
      "tools": ["search_v2", "reranking", "arxiv_search"], 
      "traffic_allocation": 50
    }
  }
}
```

### **Built-in Experimentation Features:**
- **Automatic traffic splitting** across variations based on targeting rules
- **Real-time metrics collection** for duration, tokens, satisfaction, and custom events
- **Statistical significance** tracking to determine winning variations
- **Progressive rollout** capabilities to safely deploy successful configurations

<Frame caption="A/B testing results and statistical significance tracking">
  ![LaunchDarkly Experimentation](screenshots/experimentation-results.png)
</Frame>

### **Setting Up Your Experiments**

Before running the traffic generator to collect experiment data, you need to configure the experiments in LaunchDarkly:

#### **Step 1: Create Experiment Variations**

In your LaunchDarkly dashboard:

1. **For RAG Enhancement Test**:
   - Navigate to your `support-agent` AI Config
   - Create two variations:
     - `basic-search`: Tools = `["search_v1"]`
     - `enhanced-rag`: Tools = `["search_v2", "reranking"]`

2. **For Model Efficiency Test**:
   - Create a new AI Config called `model-comparison`
   - Create two variations:
     - `openai-variant`: Model = `gpt-4o`, Tools = `["search_v2", "reranking", "arxiv_search"]`
     - `claude-variant`: Model = `claude-3-5-sonnet-20241022`, Tools = `["search_v2", "reranking", "arxiv_search"]`

<Frame caption="Setting up experiment variations in LaunchDarkly AI Configs">
  ![Experiment Setup](screenshots/experiment-setup.png)
</Frame>

#### **Step 2: Configure Traffic Allocation**

Set up 50/50 traffic splits:
- Go to the **Targeting** tab for each AI Config
- Create targeting rules with percentage rollouts
- Allocate 50% traffic to each variation

#### **Step 3: Enable Metrics Tracking**

Ensure these metrics are being tracked:
- **Duration**: Response generation time
- **Token Usage**: Input/output token consumption
- **Success Rate**: Completion success/failure
- **Custom Satisfaction**: User feedback scores

#### **Step 4: Run Experiment Traffic**

Now you can generate realistic experiment data:

<CodeBlocks>
<CodeBlock>
```bash
# Generate experiment traffic (200 queries with realistic delays)
python tools/traffic_generator.py --queries 200 --delay 1

# Monitor results in LaunchDarkly dashboard
# Wait for statistical significance (typically 100+ samples per variation)
```
</CodeBlock>
</CodeBlocks>

The traffic generator will hit both variations based on your targeting rules, creating the data you need to validate your hypotheses.


## What You've Learned

You've built a multi-agent AI system that's actually pretty impressive. Here's the tech stack you just mastered:

### **🔍 RAG (Retrieval-Augmented Generation)**
- Implemented vector search with FAISS indexing and OpenAI embeddings
- Added BM25 reranking for improved search relevance
- Created knowledge base integration with PDF processing

### **🛡️ PII Detection & Redaction** 
- Built privacy compliance workflows using native model capabilities
- Implemented geographic targeting for GDPR compliance
- Created multi-stage security checks (ingress/egress protection)

### **🔬 MCP (Model Context Protocol) Integration**
- Connected to live academic databases (ArXiv, Semantic Scholar)  
- Implemented cost-controlled access to expensive research tools
- Combined internal RAG with external research capabilities

### **🕸️ LangGraph Orchestration**
- Built complex multi-agent workflows with state management
- Implemented conditional routing and parallel processing
- Created supervisor-agent coordination patterns

### **⚙️ LaunchDarkly AI Configs**
- Achieved dynamic model selection without code deployments
- Implemented subscription-tier based tool access control
- Built real-time experimentation and metrics collection

## Next Steps

Extend and customize the system by:
- 🎨 Design an upgraded interface that inspires you
- 🧠 Update the knowledge base so your RAG-agent knows your business inside and out
- 🔌 Connect MCP tools that extend your capabilities
- 🎯 Implement targeting rules that adapt to user behavior in real-time
- 🌍 Build compliance workflows that handle different regulatory requirements
- 🛡️ Implement guardrails and cost controls that keep quality high while preventing budget surprises
- 🗣️ Create truly localized experiences with models that are optimized for your users' native languages
- 📊 Support AI configuration changes with experiments

And then every detail is now in your control with instant updates. No redeployments. No code edits. No restarts.

To get started with AI Configs, [sign up for a free trial](https://app.launchdarkly.com/signup). Questions? Reach out at `aiproduct@launchdarkly.com` and we'd love to hear what you build next.

## Related Tutorials

- 