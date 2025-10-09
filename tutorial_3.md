# Proving ROI with Data-Driven AI Agent Experiments

<div align="center">
<img src="screenshots/header.png" alt="From Guessing to Knowing - Prove ROI with Data-Driven AI Experiments" width="100%"/>
</div>

<br>

## What You'll Learn in 5 Minutes (or Build in 30)

> **Key Findings from Our Experiments:**
> - 🔴 Strict security only **decreased** positive feedback rates by 14%
> - 🔴 Claude Opus 4 performed **64% worse** than GPT-4o despite costing 33% more
> - ✅ Data-driven decisions **prevent** expensive mistakes

## The Problem

Your CEO asks: **"Is the expensive AI model worth it?"**

Your security team demands: **"Can we add stricter PII filtering?"**

You need data, not opinions. This tutorial shows you how to get it.

## The Solution: Real Experiments, Real Answers

In 30 minutes, you'll run actual A/B tests that answer:

**Does strict security hurt positive feedback rates?**
**Is Claude Opus 4 worth 33% more than GPT-4o?**

*Part 3 of 3: **Chaos to Clarity: Defensible AI Systems That Deliver***

## Quick Start Options

### **Option 1: Just Want the Concepts?** (5 min read)
Skip to [Understanding the Experiments](#understanding-your-two-experiments) to learn the methodology without running code.

### **Option 2: Full Hands-On Tutorial** (90 min)
Follow the complete guide to run your own experiments.

<details>
<summary><strong>Prerequisites for Hands-On Tutorial</strong></summary>

**Required from Previous Parts:**
- Completed Parts [1](README.md) & [2](README.md) (multi-agent system with segmentation)
- Active LaunchDarkly project with AI Configs
- API keys: Anthropic, OpenAI, LaunchDarkly

**Investment:**
- Time: ~30 minutes (15 min setup, 10 min data collection, 5 min analysis)
- Cost: $25-35 default ($5-10 with `--queries 50`)

</details>

## How the Experiments Work

**The Setup**: Your AI system will automatically test variations on simulated users, collecting real performance data that flows directly to LaunchDarkly for statistical analysis.

**The Process**:
1. **Traffic simulation** generates queries from your actual knowledge base
2. **Each user** gets randomly assigned to experiment variations
3. **AI responses** are evaluated for quality and tracked for cost/speed
4. **LaunchDarkly** calculates statistical significance automatically

**Note**: The two experiments run independently. Each user participates in both, but the results are analyzed separately.

**Pro tip**: You can stop experiments early once they reach statistical significance. In our case, we ran ~200 queries total and the premium model experiment reached significance first (99.52% confidence that GPT-4o is better). We then stopped that experiment and continued running the security experiment until it also reached significance, maximizing our statistical power while minimizing experiment runtime.

**Experiment Methodology**: Our smart supervisor agent routes queries containing PII to the security agent, while all other queries go to the support agent. All requests generate cost and performance metrics regardless of which agent handles them, ensuring comprehensive tracking for both experiments. We ran the initial 200 queries with the default 15% PII injection rate. After the premium model experiment reached significance, we turned it off and continued the security experiment with `--pii-percentage 100` to maximize the traffic reaching the security agent and accelerate statistical significance.

## Understanding Your Two Experiments

> **Before:** You guess whether stricter security helps or hurts.
> **After:** You'll have mathematical proof of user preferences.

### **Experiment 1: Security Agent Analysis**

**Question**: Does enhanced security improve safety compliance without significantly harming positive feedback rates?

**Variations** (50% each):
- **Control**: Baseline security agent (existing baseline variation)
- **Treatment**: Enhanced security agent (existing enhanced variation)

**Success Criteria (must meet 90% threshold)**:
1. ≤15% decrease in positive feedback rates
2. ≤30% cost increase
3. ≤30s response latency

### **Experiment 2: Premium Model Value Analysis**

**Question**: Does Claude Opus 4 justify its premium cost vs GPT-4o?

**Variations** (50% each):
- **Control**: GPT-4o with full tools (current version)
- **Treatment**: Claude Opus 4 with identical tools

**Success Criteria (must meet 90% threshold)**:
- ≥15% positive feedback rate improvement by Claude Opus 4
- Cost-value ratio ≥ 0.25 (positive feedback rate gain % ÷ cost increase %)

## Setting Up Metrics and Experiments

> **Why this matters:** Without metrics, you're flying blind. These five metrics reveal the truth about AI performance.

### **Step 1: Configure Metrics (5 minutes)**

#### **Quick Metric Setup**

Navigate to **Metrics** in LaunchDarkly and create three custom metrics:

| Metric | Event Key | Type | What It Measures |
|--------|-----------|------|------------------|
| **P95 Latency** | `$ld:ai:duration:total` | P95 | Response speed |
| **Avg Tokens** | `$ld:ai:tokens:total` | Average | Token usage |
| **Cost/Request** | `ai_cost_per_request` | Average | Dollar cost |
| **Positive Feedback** ✅ | Built-in | Rate | Positive feedback rate |
| **Negative Feedback** ✅ | Built-in | Rate | User complaints |

<details>
<summary><strong>See detailed setup for P95 Latency</strong></summary>

1. Event key: `$ld:ai:duration:total`
2. Type: Value/Size → Numeric, Aggregation: Sum
3. Definition: P95, value, user, sum, "lower is better"
4. Unit: `ms`, Name: `p95_total_user_latency`

<div align="center">
<img src="screenshots/user_duration.png" alt="P95 Setup" width="33%">
</div>

</details>

<details>
<summary><strong>View other metric configurations</strong></summary>

- **Tokens**: Same as latency but Average instead of P95
- **Cost**: Event key `ai_cost_per_request`, Average in dollars
- Screenshots: `screenshots/tokens.png` and `screenshots/cost.png`

</details>

The cost tracking is implemented in `utils/cost_calculator.py`, which calculates actual dollar costs using the formula `(input_tokens × input_price + output_tokens × output_price) / 1M`. The system has pre-configured pricing for each model: GPT-4o at $2.50/$10 per million tokens, Claude Opus 4 at $15/$75, and Claude Sonnet at $3/$15. When a request completes, the cost is immediately calculated and sent to LaunchDarkly as a custom event, enabling direct cost-per-user analysis in your experiments.

### **Step 2: Create Experiment Variations**

Create the experiment variations using the bootstrap script:

```bash
uv run python bootstrap/tutorial_3_experiment_variations.py
```

This creates the `claude-opus-treatment` variation for the Premium Model Value experiment. The Security Agent Analysis experiment will use your existing baseline and enhanced variations. Both experiments use the existing other-paid configuration as their control group.

### **Step 3: Configure Security Agent Experiment**

<details>
<summary>Click for details</summary>

Navigate to <strong>AI Configs → security-agent → Experiments</strong> tab → <strong>Create experiment</strong>
#### **Experiment Design**

**Experiment type:**
- Keep `Feature change` selected (default)

**Name:** `Security Level`

#### **Hypothesis and Metrics**

**Hypothesis:** `Enhanced security improves safety compliance without significantly harming positive feedback rates`

**Randomize by:** `user`

**Metrics:** Click "Select metrics or metric groups" and add:
1. `Positive feedback rate` → Select first to set as **Primary**
2. `Negative feedback rate`
3. `p95_total_user_latency`
4. `ai_cost_per_request`

#### **Audience Targeting**

**Flag or AI Config**
- Click the dropdown and select **security-agent**

**Targeting rule:**
- Click the dropdown and select **Rule 4**
- This will configure: `If Context` → `is in Segment` → `Other Paid`

#### **Audience Allocation**

**Variations served outside of this experiment:**
- `Basic Security`

**Sample size:** Set to `100%` of users in this experiment

**Variations split:** Click "Edit" and configure:
- `pii-detector`: `0%`
- `Basic Security`: `50%`
- `Strict Security`: `50%`

**Control:**
- `Basic Security`

#### **Statistical Approach and Success Criteria**

**Statistical approach:** `Bayesian`
**Threshold:** `90%`

Click **"Save"**
Click **"Start experiment"** to launch.

</details>

<br>

<div align="center">
<img src="screenshots/security_level.png" alt="Security Agent Experiment Configuration" width="75%">
</div>

<br>

### **Step 4: Configure Premium Model Experiment**

<details>
<summary>Click for details</summary>

Navigate to <strong>AI Configs → support-agent → Experiments</strong> tab → <strong>Create experiment</strong>

#### **Experiment Design**

**Experiment type:**
- Keep `Feature change` selected (default)

**Name:** `Premium Model Value Analysis`

#### **Hypothesis and Metrics**

**Hypothesis:** `Claude Opus 4 justifies premium cost with superior positive feedback rate`

**Randomize by:** `user`

**Metrics:** Click "Select metrics or metric groups" and add:
1. `Positive feedback rate` → Select first to set as **Primary**
2. `Negative feedback rate`
3. `p95_total_user_latency`
4. `average_total_user_tokens`
5. `ai_cost_per_request`

#### **Audience Targeting**

**Flag or AI Config**
- Click the dropdown and select **support-agent**

**Targeting rule:**
- Click the dropdown and select **Rule 4**
- This will configure: `If Context` → `is in Segment` → `Other Paid`

#### **Audience Allocation**

**Variations served outside of this experiment:**
- `other-paid`

**Sample size:** Set to `100%` of users in this experiment

**Variations split:** Click "Edit" and configure:
- `rag-search-enhanced`: `0%`
- `eu-free`: `0%`
- `eu-paid`: `0%`
- `other-free`: `0%`
- `other-paid`: `50%`
- `international-standard`: `0%`
- `claude-opus-treatment`: `50%`

**Control:**
- `other-paid`

#### **Statistical Approach and Success Criteria**

**Statistical approach:** `Bayesian`
**Threshold:** `90%`

Click **"Save"**
Click **"Start experiment"** to launch.

</details>

<br>

<div align="center">
<img src="screenshots/premium_model.png" alt="Premium Model Value Analysis Experiment Configuration" width="75%">
</div>

<br>

## Understanding Your Experimental Design

**Two Independent Experiments Running Concurrently:**

Since these are the **same 200 users**, each user experiences:
- One security variation (baseline OR enhanced)
- One model variation (GPT-4o OR Opus 4)

Random assignment ensures balance: ~50 users get each combination naturally.

## Generating Experiment Data

### **Step 5: Run Traffic Generator**

Start your backend and generate realistic experiment data. Choose between sequential or concurrent traffic generation:

#### **Concurrent Traffic Generator (Recommended for large datasets)**

For faster experiment data generation with parallel requests:

```bash
# Start backend API
uv run uvicorn api.main:app --reload --port 8000

# Generate experiment data with 10 concurrent requests (separate terminal)
uv run python -u tools/concurrent_traffic_generator.py --queries 200 --concurrency 10
```

**Configuration**:
- **200 queries** by default (edit script to adjust)
- **10 concurrent requests** running in parallel
- **2000-second timeout** (33 minutes) per request to handle MCP tool rate limits
- **~40-60 minutes** total runtime (vs 66+ hours sequential for 200 queries)
- **Logs saved** to `logs/concurrent_experiment_TIMESTAMP.log`

<details>
<summary>For smaller test runs or debugging</summary>

#### **Sequential Traffic Generator (Simple, one-at-a-time)**

```bash
# Start backend API
uv run uvicorn api.main:app --reload --port 8000

# Generate experiment data sequentially (separate terminal)
python tools/traffic_generator.py --queries 50 --delay 2
```

**What Happens During Simulation:**

1. **Knowledge extraction**
   Claude analyzes your docs and identifies 20+ realistic topics

2. **Query generation**
   Each test randomly selects from these topics for diversity

3. **AI-powered evaluation**
   Claude judges responses as thumbs_up/thumbs_down/neutral

4. **Automatic tracking**
   All metrics flow to LaunchDarkly in real-time

</details>

**Generation Output**:
```
📚 Analyzing knowledge base...
✅ Generated 23 topics

⚡ Sending 200 requests with 10 concurrent workers...

✅ [1/200] Success (23.4s) - other_paid: What is reinforcement learning?...
✅ [2/200] Success (45.2s) - other_paid: How does Q-learning work?...
⏱️  [15/200] Timeout (>2000s) - other_paid: Complex research query...
                              ↑ This is normal - MCP rate limits
✅ [200/200] Success (387.1s) - other_paid: Explain temporal difference...

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

## Interpreting Your Results (After Data Collection)

Once your experiments have collected data from ~100 users per variation, you'll see results in the LaunchDarkly UI. Here's how to interpret them:

### **1. Security Agent Analysis: Does enhanced security improve safety without significantly impacting positive feedback rates?**

> ## ✅ VERDICT: Switch to Strict Security
>
**Positive Feedback:** 14% decrease (8.33% to 7.21%) is within the ≤15% threshold

**Cost:** 27% increase (.1510 to .1915) is within the  ≤30% limit

**Decision Logic:**
```
IF positive_feedback_rate decrease ≤ 15%
   AND probability_to_beat for positive_feedback_rate ≥ 90%
   AND cost increase ≤ 30%
   AND probability_to_beat for cost ≥ 90%
   AND latency decrease ≤ 30s
   AND probability_to_beat for latency ≥ 90%
THEN deploy_strict_security()
ELSE keep_basic_security()
```

**Bottom line:** Both criteria met - deploy strict security.

**Read across:** Strict security cuts complaints and reduces positive feedback an acceptable amount.


**The Data That Proves It:**
<br>

<div align="center">
<img src="screenshots/security_results.png" alt="Security Level Experiment Results" width="75%"/>
</div>

<br>

### **2. Premium Model Value Analysis: Does Claude Opus 4 justify its premium cost with superior positive feedback rates?**

> ## 🔴 VERDICT: Reject Claude Opus 4
>
**Performance:** 63% WORSE positive feedback rate (5.31% vs 14.55%) 

**Probability:** 99.52% that GPT-4o is superior

**Cost:** 33% more expensive ($0.0159 vs $0.0119)

**Speed:** 81% slower (223ms vs 123ms)

**Cost-to-value Ratio:** -63%/33% = -.18

**Decision Logic:**
```
IF positive_feedback_rate increase ≥ 15%
   AND probability_to_beat for positive_feedback_rate ≥ 90%
   AND probability_to_beat for cost ≥ 90%
   AND cost-value ratio increase ≥ .25
THEN deploy_claude_opus_4()
ELSE keep_current_model()
```

**Bottom line:** Premium price delivered worse results on every metric. Experiment was stopped when positive feedbarck rate reached significance.

**Read across:** GPT-4o dominates on performance, and most likely also on speed, and cost

**The Numbers Don't Lie:**

<br>

<div align="center">
<img src="screenshots/premium_results.png" alt="Premium Model Value Analysis Results" width="75%"/>
</div>

<br>

### **Key Insights from Real Experiment Data**

**1. Test Your Assumptions**

What seems like obvious improvements often aren't; data beats intuition.

**2. Statistical Rigor Prevents Expensive Mistakes**

LaunchDarkly's statistical engine prevents costly decisions based on random variation or wishful thinking.

**3. Multiple Metrics Reveal Trade-offs**

Primary metrics tell you what to optimize for, but secondary metrics reveal the cost. Strict security did reduce complaints (-51%) but also reduced positive feedback rates. Always monitor the full picture before deciding.


## Experimental Limitations & Mitigations

**Model-as-Judge Evaluation**

We use Claude to evaluate response quality rather than real users, which represents a limitation of this experimental setup. However, research shows that model-as-judge approaches correlate well with human preferences, as documented in [Anthropic's Constitutional AI paper](https://arxiv.org/abs/2212.08073).

**Sample Size**

With approximately 100 users per variation, we're at the minimum threshold for detecting 15-20% effects reliably. For experiments where you expect smaller effects, you should increase the sample to ensure adequate statistical power.

**Independent Experiments**

While random assignment naturally balances security versions across model versions, preventing systematic bias, you cannot analyze interaction effects between security and model choices. If interaction effects are important to your use case, consider running a proper [factorial experiment design](https://en.wikipedia.org/wiki/Factorial_experiment).

**Statistical Confidence**
LaunchDarkly uses **[Bayesian statistics](https://launchdarkly.com/docs/home/experimentation/bayesian)** to calculate confidence, where 90% confidence means there's a 90% probability the true effect is positive. This is NOT the same as p-value < 0.10 from [frequentist tests](https://en.wikipedia.org/wiki/Frequentist_inference). We set the threshold at 90% (rather than 95%) to balance false positives versus false negatives, though for mission-critical features you should consider raising the confidence threshold to 95%.

## Common Mistakes We Avoided

❌ **"Let's run the experiment for a week and see"**

✅ **We defined success criteria upfront** (≥15% improvement threshold)

❌ **"Opus 4 is newer, so it must be better"**

✅ **We tested the assumption** (turned out to be 63% worse)

❌ **"This metric looks good enough to ship"**

✅ **We checked statistical confidence** (37% probability ≠ proof)

❌ **"We'll analyze the data and decide what it means"**

✅ **We predefined decision logic** (prevents rationalization)

❌ **"Premium features should help positive feedback rates"**

✅ **We measured actual impact** (strict security hurt positive feedback rates)

## What You've Accomplished

You've built a **data-driven optimization engine** with statistical rigor through falsifiable hypotheses and clear success criteria. Your predefined success criteria ensure clear decisions and prevent post-hoc rationalization. Every feature investment now has quantified business impact for ROI justification, and you have a framework for continuous optimization through ongoing measurable experimentation.

## Troubleshooting

### **Long Response Times (>20 minutes)**

If you see requests taking exceptionally long, the root cause is likely the `semantic_scholar` MCP tool hitting API rate limits, which causes 30-second retry delays. Queries using this tool may take 5-20 minutes to complete. The 2000-second timeout handles this gracefully, but if you need faster responses (60-120 seconds typical), consider removing `semantic_scholar` from tool configurations. You can verify this issue by checking logs for `HTTP/1.1 429` errors indicating rate limiting.

### **Cost Metrics Not Appearing**

If `ai_cost_per_request` events aren't showing in LaunchDarkly, first verify that `utils/cost_calculator.py` has pricing configured for your models. Cost is only tracked when requests complete successfully (not on timeout or error). The system flushes cost events to LaunchDarkly immediately after each request completion. To debug, look for `💰 COST CALCULATED:` and `COST TRACKING (async):` messages in your API logs.

## Beyond This Tutorial: Advanced AI Experimentation Patterns

### **Other AI Experimentation Types Available in LaunchDarkly**

While this tutorial focused on model selection and safety configurations, LaunchDarkly AI Configs support a comprehensive range of AI experimentation patterns:

**Prompt & Template Experiments**

Test different prompt structures, tones, and instruction sets to optimize output quality. Compare variations in few-shot examples, chain-of-thought reasoning patterns, or response formatting instructions. Measure adherence to output schemas and positive feedback rates with different communication styles.

**RAG Configuration Testing**

Experiment with retrieval parameters including reranking algorithms, and k-values for retrieval. Test different similarity thresholds, and hybrid search strategies. Measure retrieval relevance, response accuracy, and latency trade-offs.

**Tool & Function Calling Optimization**

Compare different tool exposure strategies, routing thresholds, and fallback behaviors. Test when to use external APIs versus internal knowledge, how to handle tool failures gracefully, and optimal tool selection logic. Measure tool success rates and cost implications.

**Safety Guardrail Calibration**

Beyond our basic vs. strict security example, test different combinations of content filters, red-teaming responses, and compliance checks. Experiment with moderation thresholds, harmful content detection sensitivity, and PII handling strategies while measuring false positive rates and user friction.

**Cost & Latency Trade-offs**

Run experiments comparing token budget limits, and caching strategies. Test different model routing rules based on query complexity, user segments, or time-of-day patterns. Measure cost per successful outcome rather than just cost per request.

**Advanced Practices:** Moving forward, require statistical proof before deploying any new AI configuration changes. A/B test your prompt engineering modifications to measure instruction variations with concrete outcomes. When model updates become available, compare versions using confidence intervals to ensure improvements are real. Consider exploring advanced experimental designs like [multi-armed bandits](https://launchdarkly.com/docs/home/multi-armed-bandits) for faster convergence, [sequential analysis](https://en.wikipedia.org/wiki/Sequential_analysis) for early stopping, and [factorial designs](https://docs.launchdarkly.com/guides/experimentation/designing-experiments) to understand interaction effects between multiple AI components.

## From Chaos to Clarity

Across this three-part series, you've transformed from hardcoded AI configurations to a scientifically rigorous, data-driven optimization engine. **[Part 1](tutorial_1.md)** established your foundation with a dynamic multi-agent [LangGraph](https://langchain-ai.github.io/langgraph/) system controlled by [LaunchDarkly AI Configs](https://launchdarkly.com/ai-config/), eliminating the need for code deployments when adjusting AI behavior. **[Part 2](tutorial_2.md)** added sophisticated targeting with geographic privacy rules, user segmentation by plan tiers, and [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) tool integration for real academic research capabilities. **[Part 3](tutorial_3.md)** completed your journey with statistical experimentation that proves ROI and guides optimization decisions with mathematical confidence rather than intuition.

You now possess a defensible AI system that adapts to changing requirements, scales across user segments, and continuously improves through measured experimentation. Your stakeholders receive concrete evidence for AI investments, your engineering team deploys features with statistical backing, and your users benefit from optimized experiences driven by real data rather than assumptions. The chaos of ad-hoc AI development has given way to clarity through systematic, scientific product development.

## Resources & Community

- **[LaunchDarkly Experimentation Docs](https://launchdarkly.com/docs/home/experimentation)** - Deep dive into statistical methods
- **[AI Config Best Practices](https://launchdarkly.com/docs/home/experimentation/types)** - LLM-specific patterns
- **Questions?** Open an issue in the [GitHub repo](https://github.com/anthropics/claude-code/issues)
- **Share your results** with #ai-experiments in our community Slack

---

**Remember:** Every AI decision backed by data is a risk avoided and a lesson learned. Start small, measure everything, ship with confidence.