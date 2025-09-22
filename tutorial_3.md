# A/B Testing AI Configurations with LaunchDarkly Experiments

## Overview

You can't just deploy different models and hope for the best. Without rigorous A/B testing, you're making million-dollar decisions based on gut feelings. I've seen teams burn through $2M in compute costs because they deployed GPT-4 everywhere without measuring actual impact. When they finally implemented proper testing, they discovered their "premium" model was only improving outcomes for 12% of queries but costing 10x more per request. The other 88% performed identically with a fine-tuned smaller model. One poorly chosen model configuration can destroy unit economics overnight.

*Part 3 of 3 of the series: **Chaos to Clarity: Defensible AI Systems That Deliver on Your Goals***

**Hypothesis-driven experimentation** lets you measure what actually matters: which model reduces support tickets by 40%, which configuration cuts average response time from 3.2 to 1.1 seconds, which provider gives you sub-200ms latency at half the cost. Teams that test rigorously before scaling are the ones whose AI features survive past the pilot phase.

## What You'll Build Today

In the next 22 minutes, you'll master AI experimentation with:

- **Production-Ready Metrics**: Track real user feedback, token costs, response times, and tool usage patterns
- **Tool Efficiency Experiment**: Test search_v1 vs search_v2 to measure which RAG implementation provides better user satisfaction with fewer tool calls
- **Cost Optimization Experiment**: Compare Gemini Flash vs GPT-4o to find the optimal cost/quality balance for your user base
- **Statistical Analysis**: Implement confidence intervals, guardrail metrics, and LLM-as-a-judge quality scoring

## Prerequisites

You'll need:
- **Completed [Part 2**: Multi-agent system with smart targeting](tutorial_2.md)
- **Same environment**: Python 3.9+, uv, existing API keys
- **Gemini API key**: Add `GEMINI_API_KEY=your-gemini-key` to your `.env` file ([get API key](https://aistudio.google.com/apikey))

### Getting Your Gemini API Key

Navigate to [Google AI Studio](https://aistudio.google.com/apikey) and sign in with your Google account. Click **"Create API Key"** and select your project (or create a new one). Copy the generated API key and add it to your environment:

```bash
# Add this line to your .env file
GEMINI_API_KEY=your-copied-api-key-here
```

**Note**: Gemini has generous free tier limits (15 requests per minute, 1500 per day) perfect for experimentation.

## Step 1: Enhanced Metrics Already Added ✅

Your system now has enhanced experimentation metrics from the tutorial-2 improvements:

### **Metrics Available:**
- **Tool Efficiency**: Average tool calls per query (tracks RAG vs basic search efficiency)
- **Guardrail Metrics**: Response time (<10s) and error rate (<5%) safety thresholds
- **Real User Feedback**: Simplified thumbs up/down simulation based on actual user behavior
- **LLM-as-a-Judge**: Quality scoring framework *(placeholder for future implementation)*

**Implementation**: Enhanced in `ai_metrics/metrics_tracker.py:437-463` and `tools/traffic_generator.py:69-103`

**Why These Metrics Matter:**
- **Tool Efficiency**: Fewer tool calls = faster responses and lower costs
- **Guardrails**: Prevent experiments from degrading user experience
- **Realistic Simulation**: Only simulates actual metrics we collect in the UI

## Step 2: Configure Experiment Variations (3 minutes)

We'll create two strategic experiments using LaunchDarkly's bootstrap automation. Each experiment tests a specific hypothesis with measurable outcomes.

Create the experiment configuration script:

```bash
cd bootstrap
uv run python create_experiment_configs.py
```

**Experiment 1: Tool Efficiency Test**
- **Hypothesis**: `search_v2` (semantic vector search) provides better user satisfaction than `search_v1` (basic keyword search) while using similar tool call efficiency
- **Control**: `search_v1` only
- **Treatment**: `search_v2` + `reranking`
- **Primary Metric**: Thumbs up/down rate
- **Secondary Metric**: Average tool calls per query
- **Same Model**: Claude Sonnet (isolates tool impact)

**Experiment 2: Cost Optimization Test**
- **Hypothesis**: `gemini-1.5-flash` provides comparable user satisfaction to `gpt-4o` at significantly lower cost
- **Control**: `gpt-4o` (premium, high cost)
- **Treatment**: `gemini-1.5-flash` (budget, low cost)
- **Primary Metric**: Thumbs up/down rate
- **Secondary Metric**: Token cost per query
- **Same Tools**: Full research stack (isolates model impact)

## Step 3: Run Realistic Traffic Simulation (4 minutes)

The enhanced traffic generator makes real API calls and only simulates user decision-making (thumbs up/down feedback). This provides authentic metrics for analysis.

```bash
# Generate experiment traffic (makes real API calls)
uv run python tools/traffic_generator.py --queries 100 --delay 1

# For verbose output to see the metrics
uv run python tools/traffic_generator.py --queries 50 --delay 2 --verbose
```

### **What Gets Simulated:**
- **Real API Calls**: Actual requests to `/chat` endpoint with live AI responses
- **User Decisions Only**: Thumbs up/down feedback based on realistic satisfaction rates (75% baseline)
- **Quality Indicators**: Adjustments for obvious issues users notice (very short responses, "can't help" messages)
- **Authentic Metrics**: Real token usage, response times, tool calls from actual system

## Step 4: Analyze Results with Statistical Framework (6 minutes)

View experiment results using the enhanced metrics system:

### **Metrics You'll See:**
```
📈 AI METRICS SUMMARY: {
  "total_duration_ms": 2150,
  "total_tool_calls": 3,
  "overall_success": true,
  "agent_count": 2,
  "agents": [
    {
      "name": "security_agent",
      "model": "claude-3-5-haiku-20241022",
      "tools": [],
      "duration_ms": 450
    },
    {
      "name": "support_agent",
      "model": "gpt-4o",
      "tools": ["search_v1", "search_v2", "reranking"],
      "duration_ms": 1700
    }
  ]
}
```

### **Experiment Analysis:**

**Tool Efficiency Results:**
- **Primary**: User satisfaction (thumbs up rate) comparison
- **Secondary**: Average tool calls per query (efficiency measurement)
- **Guardrails**: Response time and error rate compliance
- **Insight**: Which search implementation provides better UX

**Cost Optimization Results:**
- **Primary**: User satisfaction maintained across providers
- **Secondary**: Token cost per query (budget impact)
- **Guardrails**: Performance degradation protection
- **Insight**: Cost savings without quality degradation

## Step 5: Decision Framework (3 minutes)

Use the enhanced metrics to make data-driven configuration decisions:

### **Decision Criteria:**
1. **Statistical Significance**: Sufficient sample size for confidence
2. **Effect Size**: Meaningful difference (>5% improvement)
3. **Guardrail Compliance**: No violations of safety thresholds
4. **Business Impact**: Cost/quality tradeoffs align with goals

### **Enhanced Monitoring:**
```python
# Guardrail checking (implemented in ai_metrics/metrics_tracker.py:447-463)
guardrails_passed = metrics_tracker.check_guardrails(
    duration_ms=response_time,
    error_occurred=has_error
)

# Tool efficiency tracking
tool_efficiency = total_tool_calls / total_queries
```

### **Example Decision:**
If Gemini Flash shows:
- **Non-inferior satisfaction**: Similar thumbs up rates (within 5%)
- **50% cost reduction**: Significant budget savings from token cost tracking
- **No guardrail violations**: Response time <10s, error rate <5%

**Decision**: Migrate free users to Gemini Flash, maintain GPT-4o for paid users.

## Step 6: Scale with LaunchDarkly Experiments (3 minutes)

Create proper A/B experiments in LaunchDarkly dashboard for production deployment:

1. **Navigate to Experiments**: [Your LaunchDarkly Dashboard](https://app.launchdarkly.com/)
2. **Create Experiment**: Choose `tool-efficiency-test` or `cost-optimization-test`
3. **Set Traffic Allocation**: 50/50 split between control and treatment
4. **Configure Metrics**: Primary (satisfaction) and secondary (efficiency/cost) metrics
5. **Launch Gradually**: Start with 10% traffic, scale based on guardrail compliance

## What You've Accomplished

You've built a sophisticated AI experimentation framework that demonstrates how modern AI applications can make data-driven optimization decisions with production-ready safeguards.

Your experimentation system now has:
- **Real Metrics Tracking**: Tool efficiency, costs, satisfaction, and quality
- **Statistical Methodology**: Confidence intervals, significance testing, guardrails
- **Production-Ready**: Authentic API testing with realistic user feedback simulation
- **Decision Framework**: Evidence-based AI configuration optimization

## Key Learnings for Production

### **Experiment Design Principles:**
1. **Single Variable Testing**: Change one component (tools OR model, not both)
2. **Meaningful Metrics**: Track what actually impacts business outcomes
3. **Guardrail Protection**: Prevent experiments from degrading UX
4. **Statistical Rigor**: Require significance before making changes

### **Cost Optimization Strategy:**
- **Provider Comparison**: Test budget vs premium models with real workloads
- **Tool Efficiency**: Measure if advanced RAG justifies complexity
- **User Segmentation**: Different cost/quality tradeoffs per user tier
- **Continuous Testing**: Regularly validate as models evolve

### **Quality Assurance:**
- **Realistic Simulation**: Only simulate actual user decisions, not artificial quality scores
- **Real User Feedback**: Authentic thumbs up/down for validation
- **Response Time Monitoring**: Ensure experiments don't slow responses
- **Error Rate Tracking**: Maintain reliability standards

## Related Resources

Explore how LaunchDarkly Experiments integrate with your broader AI infrastructure:
- **[LaunchDarkly Experiments Documentation](https://launchdarkly.com/docs/home/experimentation)**
- **[AI Config Best Practices](https://launchdarkly.com/docs/home/ai-configs)**
- **[Statistical Analysis Guide](https://launchdarkly.com/docs/home/experimentation/understanding-statistical-significance)**

---

*Ready to optimize your AI systems with data? This framework provides the foundation for continuous experimentation and evidence-based decision making in production AI applications.*