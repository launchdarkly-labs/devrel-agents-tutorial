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
2. ≤5% cost increase per user (calculated from token usage × cost per token)
3. ≤2.0s response latency (completion time p95 per user)
4. 90% confidence threshold

### **Experiment 2: Premium Model Value Analysis**

**Question**: Does Claude Opus 4 justify its premium cost vs GPT-4o?

**Variations** (50% each):
- **Control**: GPT-4o with full tools (current version)
- **Treatment**: Claude Opus 4 with identical tools (current version)

**Success Criteria** (measured per user):
- ≥15% satisfaction improvement by Claude Opus 4 (positive feedback rate per user)
- Cost-value ratio ≥ 0.6 (satisfaction gain % ÷ cost increase % per user)
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

**Experiments will use these user-level metrics** with calculated decision criteria:
- **Performance constraint**: Completion time p95 per user ≤ 2.0s
- **Cost calculation per user**: Total cost = (input tokens + output tokens) × model cost per token
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
   - ≤5% cost increase per user (calculated from token usage × cost per token)
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
   - Cost-value ratio ≥ 0.6 (satisfaction gain % ÷ cost increase % per user)
   - 90% confidence threshold


## Generating Experiment Data

### **Step 5: Launch Both Experiments**

Review your experiment settings, then click "Start experiment" for both. Once active, proceed to generate data.

### **Step 6: Run Traffic Generator**

Start your backend and generate realistic experiment data:

```bash
# Start backend API
uv run uvicorn api.main:app --reload --port 8000

# Generate experiment data (separate terminal)
python tools/traffic_generator.py --queries 300 --delay 2
```

**What Happens**:
- **Knowledge base analysis**: Extracts 10+ topics from your documents
- **Random query generation**: Each query picks random topic + complexity
- **Realistic feedback**: Claude Haiku judges responses as thumbs_up/thumbs_down/no_feedback
- **LaunchDarkly data**: Feedback sent to experiments for analysis
- **Dual experiments**: Same queries feed both security agent and model experiments

**Progress Example**:
```
📚 Analyzing knowledge base...
🔍 Found 12 topics for query generation

📝 Query 1/300 | Topic: feature flags (intermediate)
🎯 Feedback: 👍 sent to LaunchDarkly

🏁 TRAFFIC GENERATION COMPLETE
📊 Total queries processed: 300
📈 Data sent to LaunchDarkly experiments
🔍 Check experiment results in LaunchDarkly dashboard
```

**Monitor Results**: Refresh your LaunchDarkly experiment "Results" tabs to see data flowing in.

## Evaluating Your Experiment Results

### **Security Agent Analysis Decision Flow**

**Step 1: Filter Qualifying Treatment**
Check if enhanced security beats baseline control using per-user metrics:
- ≥10% improvement in safety compliance (positive feedback rate per user)
- ≥90% statistical confidence
- Completion time p95 per user ≤2.0s
- Cost increase per user ≤5% (calculated from token usage × cost per token)

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

**Cost Calculation**:
- GPT-4o cost per user: $0.15 (average tokens × $15/$1M)
- Claude Opus 4 cost per user: $0.45 (average tokens × $75/$1M)
- Cost increase: 200%, Satisfaction gain: 20%, Ratio: 20%/200% = 0.1 → **Failed** (needs ≥0.6)

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