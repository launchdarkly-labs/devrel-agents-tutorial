#!/usr/bin/env python3
"""
Analyze why some requests track tokens but not costs
"""

print("""
🔍 ANALYSIS: Missing Cost Events
==================================

Your experiment shows:
- Token exposures: 145-157 ✅
- Cost events in LD: 109 ❌ (missing ~36-48)
- Cost exposures: 23-43 ❌ (missing ~102-134)

PROBLEM 1: Missing Events (145 → 109)
--------------------------------------
~36-48 requests track tokens but DON'T send cost events.

Possible causes:
1. cost = 0 (free models like Mistral)
2. model_name is missing/None
3. user_id is missing/None
4. Exception occurs after token tracking

Let's check the code flow:

In config_manager.py track_metrics_async():
  Line 236: tracker.track_tokens(token_usage)  ✅ ALWAYS happens when tokens > 0
  Line 240-261: Cost tracking only if:
    - model_name is not None/empty
    - user_id is not None/empty
    - cost > 0

DIAGNOSIS:
----------
The security agent uses Mistral (cost = 0) but might be tracking tokens.
Let me verify if security agent calls track_metrics...
""")

import subprocess
import os

os.chdir('/Users/ld_scarlett/Documents/Github/agents-demo')

# Check if security agent tracks metrics
print("\n🔍 Checking security agent metric tracking...\n")
result = subprocess.run(
    ['grep', '-n', 'track_metrics', 'agents/security_agent.py'],
    capture_output=True,
    text=True
)

if result.stdout:
    print("Security agent DOES call track_metrics:")
    print(result.stdout)
    print("\n⚠️  FOUND THE ISSUE!")
    print("Security agent tracks metrics (including tokens) but uses Mistral (cost=0)")
    print("So: tokens tracked ✅, but cost = 0 so cost event NOT sent ❌")
else:
    print("Security agent does NOT call track_metrics")

