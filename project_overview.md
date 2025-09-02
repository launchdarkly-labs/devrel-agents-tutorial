# LaunchDarkly AI Config Multi-Agent Demo

## Project Overview

This is an advanced tutorial demonstrating LaunchDarkly AI Configs with **multi-agent workflows**, **RAG integration**, and **real MCP servers**. The system showcases enterprise-grade AI agent orchestration with runtime configuration control through LaunchDarkly's platform.

The demo features a **Supervisor Agent** that orchestrates specialized **Security** and **Research** agents, each controlled by separate LaunchDarkly AI Configs, demonstrating scalable multi-agent architecture patterns.

## Core Problem Statement

Enterprise AI systems require sophisticated orchestration and runtime control:
- **Multi-Agent Coordination**: Complex workflows need intelligent routing between specialized agents
- **Performance at Scale**: RAG and research tools must deliver sub-second responses
- **Runtime Flexibility**: Organizations need to instantly adjust AI behavior without redeployment
- **Integration Standards**: Modern AI systems must leverage protocols like MCP for tool interoperability

## Solution Architecture

### LaunchDarkly LangGraph AI Configs Integration
- **3 AI Config Flags**: `supervisor-agent`, `security-agent`, `support-agent`
- **Multi-Agent Control**: Each agent configured independently for specialized behavior
- **Tool Availability**: Runtime control of RAG and MCP research tools
- **Model Selection**: Claude vs OpenAI models with per-agent configuration
- **Multi-arm Experiments**: Statistical testing of tool variations
- **Context Targeting**: Per-user/region tool access and model selection
- **All Observability**: Metrics, experiments, and monitoring centralized in LaunchDarkly

#### Support Agent Tool Variations:
- **`docs-only`**: Basic search only (`["search_v2"]`)
- **`rag-enabled`**: Full RAG stack (`["search_v2", "reranking"]`) 
- **`research-enhanced`**: RAG + MCP research (`["search_v2", "reranking", "arxiv_search", "semantic_scholar"]`)

### Key Measurement Metrics
1. **Task Success Rate**: Percentage resolved without human escalation
2. **Tool Efficiency**: Ratio of useful vs. extraneous tool calls
3. **Cost Analysis**: Total per-request costs (model + tool-specific)
4. **Latency Monitoring**: 95th percentile response times
5. **User Satisfaction**: Direct feedback collection
6. **Efficiency Score**: Composite metric balancing success vs. overhead

## Technical Components

### LaunchDarkly as Central Platform
- **AI Configs**: Model/prompt/tool configuration management
- **Experiments**: Multi-arm testing with statistical significance
- **Metrics & Observability**: All efficiency metrics flow to LaunchDarkly

### Application Components (Python)
- **FastAPI + LangGraph v0.6**: Multi-agent execution using LaunchDarkly static runtime context
- **Vector Database**: Persistent FAISS storage with OpenAI embeddings for semantic search
- **RAG Tools**: Documentation search (`search_v2`) and semantic reranking
- **MCP Research Tools**: Real academic research via Model Context Protocol
  - **ArXiv MCP Server**: Advanced academic paper search with field-specific queries and category filtering
  - **Semantic Scholar MCP Server**: Multi-database search with author profiles and citation networks
- **Multi-Agent Architecture**: Supervisor orchestrates Security and Support agents
- **Metrics Collection**: Send all events to LaunchDarkly SDK (latency, success, tool usage)
- **Chat UI**: Simple interface showing real-time tool calls and model switches

### Evaluation System
- **Query Generation**: Mixed difficulty scenarios (FAQ, ambiguous, PII-sensitive)
- **Metrics Collection**: Real-time tool usage, success rates, and cost tracking
- **Performance Analysis**: Statistical evaluation of tool effectiveness

## Repository Structure
```
/api                    # FastAPI chat service with tool orchestration
/agents                 # LangGraph agent definitions and workflows
/tools_impl             # Alternative tool implementations (lookup, search, redaction)
/policy                 # LaunchDarkly parameter reading and enforcement
/data                   # Knowledge base, PDF processing, persistent vector storage
/ui                     # Chat interface with real-time monitoring charts
/ld                     # LaunchDarkly configuration and setup automation
/tools                  # Query generation, evaluation scripts, test utilities
initialize_embeddings.py # One-time vector embedding initialization
```

## Vector Database Architecture

### Persistent Embeddings System
- **OpenAI Embeddings**: Uses `text-embedding-3-small` for superior semantic understanding
- **FAISS Storage**: CPU-optimized vector database with disk persistence
- **One-time Setup**: Run `initialize_embeddings.py` to create embeddings once
- **Automatic Loading**: Search tools automatically load pre-computed embeddings
- **No Re-computation**: Eliminates embedding computation on every tool initialization

## Experiment Design

### Variation Comparisons
- **Tool Variations**: `docs-only` vs `rag-enabled` vs `research-enhanced` (with MCP)
- **Stack Configurations**: Basic RAG vs full research capabilities
- **Model Comparisons**: Claude vs OpenAI models with same tool configurations
- **Agent Configurations**: Different multi-agent routing strategies

### Success Criteria
- Clear, evidence-based decisions on tool effectiveness
- Measurable ROI on tool implementation costs
- Justified model selection based on efficiency metrics
- Scalable policy management for production deployment

## Key Features

## Success Metrics
- Demonstrable tool ROI through controlled experiments
- Reduced operational costs through optimized configurations
- Improved user satisfaction with evidence-based tool selection
- Scalable policy management for production deployment

## Production Readiness
- **Environment Variables**: LD_SDK_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
- **Vector Storage**: Persistent FAISS database with automatic loading
- **Monitoring Integration**: LaunchDarkly metrics and custom counters
- **Policy Inheritance**: Same configuration keys for production deployment
- **No Fallbacks**: All configuration must come from LaunchDarkly (fail-fast on misconfiguration)
- **Extensibility**: Modular design for additional tools and models

This demonstrates how LaunchDarkly AI Configs enables **Speed + Caution = Iterability, Experimentation & Integration** - transforming agent development from guesswork into data-driven engineering.