# AI Metrics Tracking Guide

**Status**: ✅ **FULLY IMPLEMENTED** - LaunchDarkly AI Config metrics tracking integrated with multi-agent workflow

This document covers the comprehensive AI metrics tracking implementation that provides detailed monitoring of AI model performance across multi-agent workflows using LaunchDarkly's AI Config monitoring capabilities.

---

## 🚀 Overview

The LaunchDarkly AI Config Multi-Agent Demo now includes comprehensive AI metrics tracking that monitors:

- **Model Performance**: Duration, token usage, success/failure rates
- **Multi-Agent Workflow**: Individual agent performance within the orchestrated workflow  
- **Tool Usage**: Tracking of external vs internal tool calls
- **Real-time Monitoring**: Metrics sent to LaunchDarkly for dashboard visualization

### Key Benefits

- **Production Monitoring**: Track AI performance across different LaunchDarkly variations
- **Performance Optimization**: Identify bottlenecks in multi-agent workflows
- **Cost Management**: Monitor token usage and model costs
- **Quality Assurance**: Track success rates and error patterns

---

## 🏗️ Architecture

### Components

1. **AIMetricsTracker** (`ai_metrics/metrics_tracker.py`)
   - Central metrics collection and tracking
   - LaunchDarkly AI SDK integration
   - Multi-agent workflow coordination

2. **ConfigManager** (`policy/config_manager.py`)
   - LaunchDarkly AI Config retrieval with tracker
   - Fallback to standard flag approach when AI Config unavailable

3. **AgentService** (`api/services/agent_service.py`)
   - Workflow-level metrics tracking
   - Error handling and failure tracking

4. **Supervisor Agent** (`agents/supervisor_agent.py`)
   - Individual agent performance tracking
   - Tool usage monitoring

### Data Flow

```
User Request → AgentService → AIMetricsTracker → Multi-Agent Workflow
     ↓                ↓              ↓                    ↓
LaunchDarkly ←→ AI Config ←→ Tracker ←→ Individual Agents
     ↓
AI Config Monitoring Dashboard
```

---

## 📊 Metrics Collected

### Workflow-Level Metrics
- **Total Duration**: End-to-end workflow completion time
- **Overall Success**: Whether the entire workflow completed successfully
- **Tool Call Count**: Total number of tool invocations
- **Response Quality**: Final response length and completeness

### Agent-Level Metrics  
- **Agent Duration**: Individual agent execution time
- **Agent Success**: Per-agent success/failure status
- **Tool Usage**: Specific tools used by each agent
- **Model Performance**: Model-specific metrics per agent

### LaunchDarkly AI SDK Metrics
- **Duration Tracking**: `tracker.track_duration(milliseconds)`
- **Success/Error Tracking**: `tracker.track_success()` / `tracker.track_error()`
- **Token Usage**: `tracker.track_token_usage(input_tokens, output_tokens)`
- **Output Satisfaction**: `tracker.track_output_satisfaction(rating)`
- **Summary**: `tracker.get_summary()` for aggregated metrics

---

## 🛠️ Implementation Details

### 1. AI Metrics Tracker

```python
from ai_metrics import AIMetricsTracker

# Initialize with LaunchDarkly tracker
metrics_tracker = AIMetricsTracker(config.tracker)
metrics_tracker.start_workflow(user_id, message)

# Track individual agent
agent_start = metrics_tracker.track_agent_start("support-agent", model, variation)
# ... agent execution ...
metrics_tracker.track_agent_completion(
    "support-agent", model, variation, agent_start, 
    tool_calls, success=True
)

# Finalize workflow
final_metrics = metrics_tracker.finalize_workflow(final_response)
```

### 2. LaunchDarkly AI Config Integration

```python
# ConfigManager automatically includes tracker
config = await config_manager.get_config(user_id, "support-agent")
# config.tracker contains LaunchDarkly AI metrics tracker

# Metrics are automatically sent to LaunchDarkly AI Config monitoring
```

### 3. Multi-Agent Workflow Tracking

```python
# Supervisor agent tracks each child agent
def security_node(state):
    agent_start = metrics_tracker.track_agent_start(
        "security-agent", config.model, config.variation_key
    )
    try:
        result = security_agent.invoke(input)
        metrics_tracker.track_agent_completion(
            "security-agent", config.model, config.variation_key,
            agent_start, [], success=True
        )
    except Exception as e:
        metrics_tracker.track_agent_completion(
            "security-agent", config.model, config.variation_key,
            agent_start, [], success=False, error=str(e)
        )
```

---

## 📈 Metrics Output Examples

### Console Logging

```
🔍 AI METRICS: Starting workflow tracking for user user_001
🤖 AI METRICS: Agent supervisor-workflow started (model: claude-3-5-sonnet-20241022, variation: research-enhanced)
🤖 AI METRICS: Agent security-agent started (model: claude-3-5-sonnet-20241022, variation: pii-and-compliance)
📊 AI METRICS: Agent security-agent completed - Duration: 1250.45ms, Success: true, Tools: 0
🤖 AI METRICS: Agent support-agent started (model: claude-3-5-sonnet-20241022, variation: full-stack-claude)
🔬 MCP TOOL CALLED: search_papers (query: 'transformer architecture') (external research server)
📚 INTERNAL TOOL CALLED: search_vector (query: 'transformer models') (local processing)
📊 AI METRICS: Agent support-agent completed - Duration: 8750.23ms, Success: true, Tools: 2
✅ AI METRICS: Tracked support-agent metrics to LaunchDarkly
🚀 AI METRICS: Flushed metrics to LaunchDarkly - Duration: 10125ms
```

### Structured Metrics JSON

```json
{
  "total_duration_ms": 10125.67,
  "overall_success": true,
  "user_id": "user_001",
  "query": "Compare transformer architectures...",
  "final_response_length": 2453,
  "total_tool_calls": 2,
  "agent_count": 3,
  "agents": [
    {
      "name": "supervisor-workflow",
      "model": "claude-3-5-sonnet-20241022",
      "variation": "research-enhanced", 
      "duration_ms": 10125.67,
      "tools": ["search_papers", "search_vector"],
      "success": true,
      "tokens": null
    },
    {
      "name": "security-agent",
      "model": "claude-3-5-sonnet-20241022",
      "variation": "pii-and-compliance",
      "duration_ms": 1250.45,
      "tools": [],
      "success": true,
      "tokens": null
    },
    {
      "name": "support-agent", 
      "model": "claude-3-5-sonnet-20241022",
      "variation": "full-stack-claude",
      "duration_ms": 8750.23,
      "tools": ["search_papers", "search_vector"],
      "success": true,
      "tokens": null
    }
  ]
}
```

---

## 🎯 LaunchDarkly Configuration

### AI Config Structure for Metrics

```json
{
  "model": {
    "name": "claude-3-5-sonnet-20241022",
    "parameters": {
      "tools": [
        {
          "name": "search_v2",
          "description": "📚 INTERNAL: Advanced vector search",
          "type": "function"
        },
        {
          "name": "arxiv_search", 
          "description": "🔬 MCP: ArXiv research papers",
          "type": "function"
        }
      ]
    },
    "custom": {
      "max_tool_calls": 8,
      "max_cost": 1.0
    }
  },
  "instructions": "You are a research assistant...",
  "_ldMeta": {
    "variationKey": "research-enhanced"
  }
}
```

### Metrics Visualization

Metrics are automatically sent to **LaunchDarkly AI Config Monitoring tab** where you can view:

- **Duration Trends**: Average response times across variations
- **Success Rates**: Error rates and failure patterns  
- **Token Usage**: Cost tracking and optimization opportunities
- **Satisfaction Scores**: Quality metrics and user satisfaction
- **Variation Comparison**: A/B test performance analysis

---

## 🔧 Configuration Options

### Environment Variables

```bash
# Required for metrics tracking
LD_SDK_KEY=your_launchdarkly_key
ANTHROPIC_API_KEY=your_anthropic_key

# Optional: Override default AI Config keys
LAUNCHDARKLY_AI_CONFIG_KEY=support-agent
```

### Customization Points

1. **Metrics Collection**: Modify `AIMetricsTracker` to add custom metrics
2. **Tool Categorization**: Update emoji indicators and categorization logic
3. **Aggregation**: Adjust metrics aggregation and summary formats
4. **Sampling**: Add metrics sampling for high-volume scenarios

---

## 🧪 Testing

### Verify Metrics Tracking

```bash
# Test with research query
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Find recent papers on reinforcement learning"
  }'

# Look for metrics logs:
# 🔍 AI METRICS: Starting workflow tracking
# 📊 AI METRICS: Agent xxx completed - Duration: xxxms
# 🚀 AI METRICS: Flushed metrics to LaunchDarkly
```

### LaunchDarkly Monitoring

1. Open LaunchDarkly dashboard
2. Navigate to AI Configs → Your config → Monitoring tab
3. Verify metrics appear:
   - Duration graphs
   - Success rate metrics
   - Tool usage statistics
   - Error tracking

---

## 🛠️ Troubleshooting

### Common Issues

**Metrics Not Appearing in LaunchDarkly:**
- Verify LaunchDarkly AI SDK is properly configured
- Check that AI Config is enabled (not just flag variation)
- Ensure network connectivity to LaunchDarkly

**Missing Agent Metrics:**
- Check console logs for tracker initialization
- Verify agent completion tracking is called
- Look for error messages in workflow execution

**Performance Impact:**
- Metrics tracking adds minimal overhead (~10-50ms per request)
- Uses background flushing to LaunchDarkly
- Graceful degradation when metrics fail

### Debug Commands

```bash
# Check AI SDK installation
uv run python -c "from ldai.client import LDAIClient; print('✅ AI SDK Ready')"

# Verify LaunchDarkly connection
uv run python -c "import ldclient; print('✅ LaunchDarkly SDK Ready')"

# Test metrics tracker
uv run python -c "from ai_metrics import AIMetricsTracker; print('✅ Metrics Tracker Ready')"
```

---

## 🚀 Production Deployment

### Best Practices

1. **Monitoring Setup**: Configure LaunchDarkly alerts for error rate thresholds
2. **Cost Tracking**: Monitor token usage trends and set budgets
3. **Performance Baselines**: Establish SLA benchmarks for response times
4. **Error Analysis**: Use metrics to identify and resolve recurring issues

### Scaling Considerations

- **High Volume**: Consider metrics sampling at >1000 requests/minute
- **Multi-Region**: Metrics automatically route to correct LaunchDarkly environment
- **Cost Optimization**: Use metrics to optimize model selection and tool usage

---

## ✅ Implementation Complete

**The LaunchDarkly AI Config Multi-Agent Demo now includes:**

- ✅ **Comprehensive AI Metrics**: Full workflow and agent-level tracking
- ✅ **LaunchDarkly Integration**: Real-time metrics in AI Config monitoring
- ✅ **Multi-Agent Support**: Individual agent performance tracking
- ✅ **Tool Usage Monitoring**: External vs internal tool categorization  
- ✅ **Error Handling**: Graceful failure tracking and recovery
- ✅ **Production Ready**: Minimal overhead with background processing

**Ready for comprehensive AI performance monitoring and optimization! 📊**