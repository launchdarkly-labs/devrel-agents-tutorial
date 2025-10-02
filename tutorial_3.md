# Proving ROI with Data-Driven AI Agent Experiments

## Overview

You've built a sophisticated multi-agent system with smart targeting and premium research tools. What you and every AI product team now face is: stakeholders need concrete proof that advanced features deliver measurable value. They want to see hard numbers showing that premium search tools increase user satisfaction and that expensive models use resources more efficiently.

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

## ⚠️ Cost Warning

> **IMPORTANT: This tutorial costs approximately $40 with default settings**
>
> The expense comes from using Claude Opus 4 ($15/$75 per 1M tokens) and generating 200+ completions for statistical significance. To reduce costs to $5-10, switch to Claude Sonnet 3.5 or GPT-4o-mini by editing the model settings in `bootstrap/tutorial_3_experiment_variations.py`, or use `--queries 50` instead of 200 when running the traffic generator.

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

## Setting Up Metrics and Experiments

### **Step 1: Configure Metrics**

Navigate to **Metrics** and create these five metrics:

#### **Metric 1: P95 User Latency**

![P95 User Latency Metric Configuration](screenshots/user_duration.png)

> **Event key:** `$ld:ai:duration:total`
>
> **What do you want to measure:** `Value / Size` → `Numeric`
>
> **Aggregation:** `Sum`
>
> **Metric definition:** `P95` `value` of the per `user` event `sum`, where `lower is better`
>
> **Unit of measure:** `ms`
>
> **Metric name:** `p95_total_user_latency`
>
> **Metric key:** `user_latency`

#### **Metric 2: Average Total Tokens**

![Average Total Tokens Metric Configuration](screenshots/tokens.png)

> **Event key:** `$ld:ai:tokens:total`
>
> **What do you want to measure:** `Value / Size` → `Numeric`
>
> **Aggregation:** `Average`
>
> **Metric definition:** `Average` `value` of the per `user` event `sum`, where `lower is better`
>
> **Unit of measure:** `tokens`
>
> **Metric name:** `average_total_user_tokens`
>
> **Metric key:** `average_tokens`

#### **Metric 3: Positive Feedback Rate**

> **Event key:** `$ld:ai:feedback:positive`
>
> **What do you want to measure:** `Count`
>
> **Metric definition:** `Conversion rate` where `higher is better`
>
> **Metric name:** `positive.feedback.rate`
>
> **Metric key:** `positive_feedback`

#### **Metric 4: Negative Feedback Rate**

> **Event key:** `$ld:ai:feedback:negative`
>
> **What do you want to measure:** `Count`
>
> **Metric definition:** `Conversion rate` where `lower is better`
>
> **Metric name:** `negative.feedback.rate`
>
> **Metric key:** `negative_feedback`

#### **Metric 5: AI Cost Per Request**

![AI Cost Per Request Metric Configuration](screenshots/cost.png)

> **Event key:** `ai_cost_per_request`
>
> **What do you want to measure:** `Value / Size` → `Numeric`
>
> **Aggregation:** `Average`
>
> **Metric definition:** `Average` `value` of the per `user` event `sum`, where `lower is better`
>
> **Unit of measure:** `$`
>
> **Metric name:** `ai_cost_per_request`
>
> **Metric key:** `ai_cost`

**Important:** Click "Create metric" and ensure it shows as "Production" environment.

The cost tracking is implemented in `utils/cost_calculator.py`, which calculates actual dollar costs using the formula `(input_tokens × input_price + output_tokens × output_price) / 1M`. The system has pre-configured pricing for each model: GPT-4o at $2.50/$10 per million tokens, Claude Opus 4 at $15/$75, and Claude Sonnet at $3/$15. When a request completes, the cost is immediately calculated and sent to LaunchDarkly as a custom event, enabling direct cost-per-user analysis in your experiments.

### **Step 2: Create Experiment Variations**

Create the experiment variations using the bootstrap script:

```bash
uv run python bootstrap/tutorial_3_experiment_variations.py
```

This creates variations for the premium model experiment:
- **Premium Model Value**: `claude-opus-treatment`
- **Security Agent Analysis**: Uses existing baseline and enhanced variations
- **Note**: Both experiments use existing other-paid configuration as control

### **Step 3: Configure Security Agent Experiment**

![Security Agent Experiment Configuration](screenshots/security_level.png)

Navigate to **AI Configs → security-agent → Create experiment**. You'll see a 4-step configuration flow:

#### **Section 1: Experiment Details**

Fill in these fields:

> **Experiment name:**
> ```
> Security Level
> ```
>
> **Hypothesis:**
> ```
> Strict security agent will cause a loss of context and reduce user satisfaction
> ```

#### **Section 2: Select Metrics**

Click the metrics dropdown and add:

> **Primary metric:** `positive.feedback.rate`
>
> **Secondary metrics:**
> - `p95_total_user_latency`
> - `average_total_user_tokens`
> - `negative.feedback.rate`

#### **Section 3: Define Audience**

The AI Config `security-agent` is pre-selected. Add targeting:

> **Targeting rule:** Select `If Context` → `is in Segment` → `Other Paid`

#### **Section 4: Confirm Allocation**

Enable absolute percentage display:

> **☑ Show absolute percentage**
>
> **100%** of `user` contexts are in this experiment

Click **"Allocation split"** to configure variations:

> **Basic Security** (Control): `50%` → Select variation: `baseline`
>
> **Strict Security** (Treatment): `50%` → Select variation: `enhanced`

Review and click **"Start experiment"** to launch.

#### **Success Criteria to Monitor**
- ≥10% improvement in positive feedback rate
- ≤5% cost increase (track via `ai_cost_per_request` metric)
- ≤2.0s p95 latency
- 90% statistical confidence

### **Step 4: Configure Premium Model Experiment**

![Premium Model Value Analysis Experiment Configuration](screenshots/premium_model.png)

Navigate to **AI Configs → support-agent → Create experiment**. Follow the same 4-step flow:

#### **Section 1: Experiment Details**

Fill in these fields:

> **Experiment name:**
> ```
> Premium Model Value Analysis
> ```
>
> **Hypothesis:**
> ```
> Claude Opus 4 justifies premium cost with superior satisfaction
> ```

#### **Section 2: Select Metrics**

Click the metrics dropdown and add:

> **Primary metric:** `positive.feedback.rate`
>
> **Secondary metrics:**
> - `negative.feedback.rate`
> - `p95_total_user_latency`
> - `average_total_user_tokens`
> - `ai_cost_per_request`

#### **Section 3: Define Audience**

The AI Config `support-agent` is pre-selected. Add targeting:

> **Targeting rule:** Select `If Context` → `is in Segment` → `Other Paid`

#### **Section 4: Confirm Allocation**

Enable absolute percentage display:

> **☑ Show absolute percentage**
>
> **100%** of `user` contexts are in this experiment

Click **"Allocation split"** to configure variations:

> **Other Paid** (Control): `50%` → Select variation: `other-paid`
>
> **Claude Opus 4 Treatment** (Treatment): `50%` → Select variation: `claude-opus-treatment`

Review and click **"Start experiment"** to launch.

#### **Success Criteria to Monitor**
- ≥15% satisfaction improvement (positive feedback rate)
- Cost-value ratio ≥ 0.6 (satisfaction % ÷ cost increase %)
- 90% statistical confidence


## Generating Experiment Data

### **Step 5: Launch Both Experiments**

1. **Review Settings**: Verify all configurations match the templates above
2. **Start Security Experiment**: Click "Start experiment" on Security Level
3. **Start Model Experiment**: Click "Start experiment" on Premium Model Value Analysis
4. **Verify Status**: Both should show "Running" in the experiments list
5. **Check Metrics**: Navigate to Metrics tab and verify:
   - Built-in metrics show "Leading: [experiment name]"
   - Custom `ai_cost_per_request` metric shows both experiments connected

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
- **AI-powered feedback**: Claude evaluates each response to determine if a user would give positive/negative/no feedback based on answer quality
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