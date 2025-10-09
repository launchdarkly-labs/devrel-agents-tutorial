# Cost Metrics Fix - Root Cause Analysis

## Problem
Cost metrics (`ai_cost_per_request`) were showing up in LaunchDarkly's metrics tracking UI but **not appearing in experiment results**.

## Root Cause

### What Broke (Commit a79869b - Oct 9, 2025)

**Commit:** `a79869b - "revise cost tracking"`

This commit removed centralized tracking methods from `config_manager.py`:
- Removed `track_metrics()` method (-86 lines)
- Removed `track_metrics_async()` method (-85 lines)
- Moved cost tracking into individual agents

### The Context Mismatch

**Before the fix, there was a critical mismatch:**

1. **AI Config Evaluation Context** (`config_manager.get_config()`):
   ```python
   # Only set specific attributes
   if 'country' in user_context:
       context_builder.set('country', user_context['country'])
   if 'plan' in user_context:
       context_builder.set('plan', user_context['plan'])
   if 'region' in user_context:
       context_builder.set('region', user_context['region'])
   ```

2. **Cost Tracking Context** (in each agent):
   ```python
   # Set ALL attributes
   if user_context:
       for key, value in user_context.items():
           context_builder.set(key, value)
   ```

**Result:** Events included `user` attribute but AI Config didn't → **Experiment association failed**

## The Fix

### 1. Centralized Context Building (`config_manager.py`)

Added new method to ensure consistency:

```python
def build_context(self, user_id: str, user_context: dict = None) -> Context:
    """Build a LaunchDarkly context with consistent attributes.
    
    This ensures the same context is used for both AI Config evaluation
    and custom metric tracking, which is required for experiment association.
    """
    context_builder = Context.builder(user_id).kind('user')
    
    if user_context:
        # Set all attributes from user_context for consistency
        for key, value in user_context.items():
            context_builder.set(key, value)
    
    return context_builder.build()
```

### 2. Updated All Agents

Modified cost tracking in:
- ✅ `agents/supervisor_agent.py`
- ✅ `agents/security_agent.py`  
- ✅ `agents/ld_agent_helpers.py` (support agent)

**Old Pattern:**
```python
context_builder = Context.builder(user_id).kind('user')
if user_context:
    for key, value in user_context.items():
        context_builder.set(key, value)
ld_context = context_builder.build()
```

**New Pattern:**
```python
# Use centralized builder
ld_context = config_manager.build_context(user_id, user_context)
```

## Why This Matters for Experiments

LaunchDarkly experiments require:
1. **Same context** for AI Config evaluation and metric events
2. **Identical attributes** on both contexts
3. **Same user_id** (context key)

When contexts don't match exactly, the experiment system can't associate custom metric events with the specific AI Config variation, so they appear in metrics UI but not in experiment results.

## Verification

Your event JSON shows the issue:
```json
{
  "contexts": [
    {
      "context_key": "user_1760025262_361",
      "attributes_json": "{\"country\":\"US\",\"region\":\"other\",\"plan\":\"paid\",\"user\":\"user_1760025262_361\"}"
    }
  ]
}
```

The `user` attribute was being set for cost tracking but not for AI Config evaluation, causing the mismatch.

## Testing the Fix

1. **Restart your backend:**
   ```bash
   uv run uvicorn api.main:app --reload --port 8000
   ```

2. **Generate new test traffic:**
   ```bash
   uv run python -u tools/concurrent_traffic_generator.py --queries 10 --concurrency 2
   ```

3. **Check LaunchDarkly:**
   - Navigate to your experiments
   - Cost metrics should now appear in experiment results
   - Events should be properly attributed to variations

## What Changed

| File | Lines Changed | Description |
|------|---------------|-------------|
| `config_manager.py` | +14 | Added `build_context()` method |
| `agents/supervisor_agent.py` | -8, +3 | Use centralized context builder |
| `agents/security_agent.py` | -8, +3 | Use centralized context builder |
| `agents/ld_agent_helpers.py` | -7, +2 | Use centralized context builder |

## Key Takeaway

**For LaunchDarkly AI Config experiments:** Always use the **exact same context** (with identical attributes) for both:
1. AI Config evaluation (`ai_client.agent(config, context)`)
2. Custom metric tracking (`ld_client.track(event, context, ...)`)

Context mismatches break experiment attribution even though events still appear in the metrics UI.

