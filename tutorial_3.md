# Proving ROI with Data-Driven AI Agent Experiments

## Overview

You've built a sophisticated multi-agent system with smart targeting and premium research tools. But here's what every AI product team faces: stakeholders need concrete proof that advanced features deliver measurable value. They want to see hard numbers showing that premium search tools increase user satisfaction and that expensive models use resources more efficiently.

*Part 3 of 3 of the series: **Chaos to Clarity: Defensible AI Systems That Deliver on Your Goals***

The solution? **Rigorous A/B experiments** with specific hypotheses and clear success criteria. Instead of guessing which configurations work better, you'll run two strategic experiments that prove ROI with scientific rigor: tool implementation impact and model efficiency analysis.

## What You'll Prove Today

In the next 25 minutes, you'll design and execute experiments that answer two critical business questions:

- **Security Agent Analysis**: Does enhanced security improve safety without significantly impacting user satisfaction?
- **Premium Model Value Analysis**: Does Claude Opus 4 justify its premium cost with superior user satisfaction for paid users?

## Prerequisites

> **⚠️ CRITICAL: Required Previous Steps**

You'll need:
- **Completed Parts 1 & 2**: Working multi-agent system with segmentation
- **Active LaunchDarkly Project**: With AI Configs and user segments from Part 2
- **API Keys**: All keys from previous parts (Anthropic, OpenAI, LaunchDarkly, Mistral)

## Data Foundation

**Realistic Experiment Data**: We'll target other-paid users (non-EU countries, paid tier) with queries randomly selected from YOUR knowledge base topics. The system uses 3-option feedback simulation (thumbs_up/thumbs_down/no_feedback) matching real user patterns, sending feedback data to LaunchDarkly for experiment analysis.

## Understanding Your Two Experiments

### **Experiment 1: Security Agent Analysis**

**Question**: Does strict security cause a loss of context and reduce user satisfaction?

**Variations** (50% each):
- **Control**: Baseline security agent (existing baseline variation)
- **Treatment**: Enhanced security agent (existing enhanced variation)

**Success Criteria** (measured per user):
1. ≥10% improvement in safety compliance (positive feedback rate per user)
2. ≤5% cost increase per user (from `ai_cost_per_request` custom metric tracking actual $ cost)
3. ≤2.0s response latency (completion time p95 per user)
4. 90% confidence threshold

### **Experiment 2: Premium Model Value Analysis**

**Question**: Does Claude Opus 4 justify its premium cost vs GPT-4o?

**Variations** (50% each):
- **Control**: GPT-4o with full tools (current version)
- **Treatment**: Claude Opus 4 with identical tools (current version)

**Success Criteria** (measured per user):
- ≥15% satisfaction improvement by Claude Opus 4 (positive feedback rate per user)
- Cost-value ratio ≥ 0.6 (satisfaction gain % ÷ cost increase % per user, using real $ from `ai_cost_per_request`)
- 90% confidence threshold

## Setting Up Both Experiments

### **Step 1: Create Experiment Variations**

Create the experiment variations using the bootstrap script:

```bash
uv run python bootstrap/tutorial_3_experiment_variations.py
```

This creates variations for the premium model experiment:
- **Premium Model Value**: `claude-opus-treatment`
- **Security Agent Analysis**: Uses existing baseline and enhanced variations
- **Note**: Both experiments use existing other-paid configuration as control

### **Step 2: Use Built-in AI Metrics (Per User)**

LaunchDarkly AI SDK automatically tracks these user-level metrics when your system runs. No setup needed - they're created automatically:

**Available Built-in Metrics:**
- **Input tokens per user (average)** - tracks average input cost per user
- **Output tokens per user (average)** - tracks average output cost per user
- **Completion time p95 per user** - tracks 95th percentile response latency per user
- **Positive feedback count per user** - tracks user satisfaction events
- **Negative feedback count per user** - tracks user dissatisfaction events

**Custom Cost Metrics:**
This implementation also tracks **actual dollar costs per request** using a custom metric:
- **ai_cost_per_request** - calculates real cost based on: `(input_tokens × input_price + output_tokens × output_price) / 1M`
- Model pricing automatically configured for GPT-4o ($2.50/$10), Claude Opus 4 ($15/$75), etc.
- Cost tracked immediately when each request completes
- Enables direct cost-per-user analysis in experiments

**Experiments will use these user-level metrics** with calculated decision criteria:
- **Performance constraint**: Completion time p95 per user ≤ 2.0s
- **Cost calculation per user**: Average `ai_cost_per_request` events per user
- **Satisfaction rate per user**: Positive feedback / (positive + negative feedback)
- **Cost-value ratio**: Satisfaction improvement % ÷ cost increase % (calculated post-experiment)

### **Step 3: Configure Security Agent Experiment**

1. **Navigate to AI Configs** → **security-agent** → **Create experiment**
2. **Experiment Setup**:
   - **Name**: `Security Agent Analysis`
   - **Hypothesis**: `Strict security agent will cause a loss of context and reduce user satisfaction`
   - **Metrics**:
     - **Primary**: Positive feedback rate per user
     - **Secondary**: Input tokens per user, Output tokens per user, Completion time p95 per user
   - **Audience**:
     - **AI Config**: security-agent
     - **Targeting rule**: If Context is in Segment Other Paid
   - **Allocation**: 100% sample size

3. **Configure Two Variations** (50% each):
   - **Control**: Use existing baseline variation
   - **Treatment**: Use existing enhanced variation

4. **Statistical Approach**:
   - **Type**: Bayesian experiment
   - **Threshold**: 95% threshold
   - **Credible interval**: 90% credible interval

5. **Success Criteria**:
   - ≥10% improvement in safety compliance (positive feedback rate per user)
   - ≤5% cost increase per user (from `ai_cost_per_request` custom metric)
   - ≤2.0s response latency (completion time p95 per user)
   - 90% confidence threshold

### **Step 4: Configure Premium Model Experiment**

1. **Navigate to AI Configs** → **support-agent** → **Create experiment**
2. **Experiment Setup**:
   - **Name**: `Premium Model Value Analysis`
   - **Hypothesis**: `Claude Opus 4 justifies premium cost with superior satisfaction`
   - **Metrics**:
     - **Primary**: Total tokens per completion (users)
     - **Secondary**: Positive feedback rate, Negative feedback rate, user latency
   - **Audience**:
     - **AI Config**: support-agent
     - **Targeting rule**: If Context is in Segment Other Paid
   - **Allocation**: 100% sample size

3. **Configure Two Variations** (50% each):
   - **Control**: Use existing other-paid variation (GPT-4o with full tools)
   - **Treatment**: `claude-opus-treatment` (Claude Opus 4 with identical tools)

4. **Statistical Approach**:
   - **Type**: Bayesian experiment
   - **Threshold**: 95% threshold
   - **Credible interval**: 90% credible interval

5. **Success Criteria**:
   - ≥15% satisfaction improvement by Claude Opus 4 (positive feedback rate per user)
   - Cost-value ratio ≥ 0.6 (satisfaction gain % ÷ cost increase % per user, using `ai_cost_per_request`)
   - 90% confidence threshold


## Generating Experiment Data

### **Step 5: Launch Both Experiments**

Review your experiment settings, then click "Start experiment" for both. Once active, proceed to generate data.

### **Step 6: Run Traffic Generator**

Start your backend and generate realistic experiment data. Choose between sequential or concurrent traffic generation:

#### **Option A: Concurrent Traffic Generator (Recommended for large datasets)**

For faster experiment data generation with parallel requests:

```bash
# Start backend API
uv run uvicorn api.main:app --reload --port 8000

# Generate experiment data with 10 concurrent requests (separate terminal)
./run_experiment_concurrent.sh
```

**Configuration**:
- **200 queries** by default (edit script to adjust)
- **10 concurrent requests** running in parallel
- **2000-second timeout** (33 minutes) per request to handle MCP tool rate limits
- **~40-60 minutes** total runtime (vs 66+ hours sequential for 200 queries)
- **Logs saved** to `logs/concurrent_experiment_TIMESTAMP.log`

Alternatively, run directly with custom settings:
```bash
uv run python -u tools/concurrent_traffic_generator.py --queries 200 --concurrency 10
```

#### **Option B: Sequential Traffic Generator (Simple, one-at-a-time)**

For smaller test runs or debugging:

```bash
# Start backend API
uv run uvicorn api.main:app --reload --port 8000

# Generate experiment data sequentially (separate terminal)
python tools/traffic_generator.py --queries 50 --delay 2
```

**What Happens (Both Options)**:
- **Knowledge base analysis**: Extracts 20+ topics from your documents using Claude
- **Random query generation**: Each query picks random topic from analyzed KB
- **Realistic feedback**: 80% positive, 20% negative (simulating real user patterns)
- **LaunchDarkly data**: Feedback and cost metrics sent to experiments for analysis
- **Dual experiments**: Same queries feed both security agent and model experiments
- **Cost tracking**: Real dollar costs calculated and tracked per request

**Progress Example (Concurrent)**:
```
📚 Analyzing knowledge base...
✅ Generated 23 topics

⚡ Sending 200 requests with 10 concurrent workers...

✅ [1/200] Success (23.4s) - other_paid: What is reinforcement learning?...
✅ [2/200] Success (45.2s) - other_paid: How does Q-learning work?...
⏱️  [15/200] Timeout (>2000s) - other_paid: Complex research query...
✅ [200/200] Success (387.1s) - eu_paid: Explain temporal difference...

======================================================================
✅ COMPLETE
======================================================================
Total time: 45.3 minutes (2718s)
Successful: 195/200 (97.5%)
Failed: 5/200 (2.5%)
Average: 13.6s per query (with concurrency)
```

**Performance Notes**:
- Most queries complete in 10-60 seconds
- Queries using `semantic_scholar` MCP tool may take 5-20 minutes due to API rate limits
- Concurrent execution handles slow requests gracefully by continuing with others
- Failed/timeout requests (<5% typically) don't affect experiment validity

**Monitor Results**: Refresh your LaunchDarkly experiment "Results" tabs to see data flowing in. Cost metrics appear as custom events alongside feedback and token metrics.

## Evaluating Your Experiment Results

### **Security Agent Analysis Decision Flow**

**Step 1: Filter Qualifying Treatment**
Check if enhanced security beats baseline control using per-user metrics:
- ≥10% improvement in safety compliance (positive feedback rate per user)
- ≥90% statistical confidence
- Completion time p95 per user ≤2.0s
- Cost increase per user ≤5% (from `ai_cost_per_request` metric average)

**Step 2: Make Security Decision**
- If enhanced security qualifies: Deploy enhanced security to all users
- If enhanced security fails: Keep baseline security for cost efficiency

**Example Results** (per-user metrics):
- **Control**: Baseline security agent performance per user
- **Treatment**: Enhanced security shows 12% safety improvement per user, 94% confidence, 1.6s p95, 3% cost increase per user → **Qualifies**

**Decision**: Deploy enhanced security agent - meets safety improvement threshold with acceptable cost/latency trade-offs.

### **Premium Model Value Decision Flow**

**Step 1: Filter Qualifying Treatment**
Check if Claude Opus 4 beats GPT-4o control using per-user metrics:
- ≥15% satisfaction improvement vs GPT-4o (positive feedback rate per user)
- ≥90% statistical confidence
- Cost-value ratio ≥ 0.6 (satisfaction gain % ÷ cost increase % per user)

**Step 2: Make Model Decision**
- If Claude Opus 4 qualifies: Switch premium users to Claude Opus 4
- If Claude Opus 4 fails: Keep GPT-4o for cost efficiency

**Example Results** (per-user metrics):
- **Control**: GPT-4o baseline performance per user
- **Treatment**: Claude Opus 4 shows 20% satisfaction improvement per user, 95% confidence, cost-value ratio 0.8 → **Qualifies**

**Cost Calculation** (using `ai_cost_per_request` metric):
- GPT-4o cost per user: $0.15 average (from tracked `ai_cost_per_request` events)
- Claude Opus 4 cost per user: $0.45 average (from tracked `ai_cost_per_request` events)
- Cost increase: 200%, Satisfaction gain: 20%, Ratio: 20%/200% = 0.1 → **Failed** (needs ≥0.6)

**Note**: The `ai_cost_per_request` custom metric automatically calculates real dollar costs using:
- GPT-4o: $2.50 input / $10 output per 1M tokens
- Claude Opus 4: $15 input / $75 output per 1M tokens
- Claude Sonnet 3.5: $3 input / $15 output per 1M tokens

**Decision**: Keep GPT-4o - Claude Opus 4 doesn't justify cost per user.

## What You've Accomplished

You've built a **data-driven optimization engine** with:
- **Statistical rigor**: Falsifiable hypotheses with confidence thresholds
- **Clear decisions**: Predefined success criteria prevent post-hoc rationalization
- **ROI justification**: Quantified business impact for feature investments
- **Continuous optimization**: Framework for ongoing measurable experimentation

**Typical Results**:
- **Advanced tools**: 15-30% satisfaction improvement, most pronounced on complex queries
- **Premium models**: 15-25% satisfaction improvement when cost-value ratio ≥ 0.6

## Troubleshooting

### **Long Response Times (>20 minutes)**

If you see requests taking exceptionally long:
- **Root cause**: The `semantic_scholar` MCP tool can hit API rate limits, causing 30-second retry delays
- **Impact**: Queries using this tool may take 5-20 minutes to complete
- **Solution**: The 2000-second timeout handles this gracefully
- **Alternative**: Remove `semantic_scholar` from tool configurations for faster responses (60-120 seconds typical)
- **Verification**: Check logs for `HTTP/1.1 429` errors indicating rate limiting

### **Cost Metrics Not Appearing**

If `ai_cost_per_request` events aren't showing in LaunchDarkly:
- **Verify model pricing**: Check `utils/cost_calculator.py` has pricing for your models
- **Check completion**: Cost only tracked when requests complete successfully (not timeout/error)
- **LaunchDarkly flush**: Cost events flush immediately after each request completion
- **Debug logging**: Look for `💰 COST CALCULATED:` and `COST TRACKING (async):` in API logs

## Beyond This Tutorial

**Next Steps**:
- **New tools**: Require statistical proof before production deployment
- **Prompt engineering**: A/B test instruction variations with measurable outcomes
- **Model updates**: Compare versions with confidence intervals
- **Advanced designs**: Multi-armed bandits, sequential analysis, interaction effects

## From Chaos to Clarity

Across this three-part series, you've transformed from hardcoded AI configurations to a scientifically rigorous, data-driven optimization engine. **Part 1** established your foundation with a dynamic multi-agent LangGraph system controlled by LaunchDarkly AI Configs, eliminating the need for code deployments when adjusting AI behavior. **Part 2** added sophisticated targeting with geographic privacy rules, user segmentation by plan tiers, and MCP tool integration for real academic research capabilities. **Part 3** completed your journey with statistical experimentation that proves ROI and guides optimization decisions with mathematical confidence rather than intuition.

You now possess a defensible AI system that adapts to changing requirements, scales across user segments, and continuously improves through measured experimentation. Your stakeholders receive concrete evidence for AI investments, your engineering team deploys features with statistical backing, and your users benefit from optimized experiences driven by real data rather than assumptions. The chaos of ad-hoc AI development has given way to clarity through systematic, scientific product development.

## Related Resources

Explore **[LaunchDarkly Experimentation](https://launchdarkly.com/docs/home/experimentation)** for advanced statistical analysis and **[AI Config Experiments](https://launchdarkly.com/docs/home/experimentation/types)** for LLM-specific testing methodologies.

---

*Ready to ship AI products that prove their own value? Your framework is built, your experiments are running, and your data-driven optimization journey begins now.*