#!/usr/bin/env python3
"""
Simple script to see why costs aren't being tracked
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = f"http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}"

print("🔍 Testing Cost Tracking Issues\n")
print("=" * 70)

# Send one test request
query = {
    "user_id": "debug_user_001",
    "message": "What is reinforcement learning?",
    "user_context": {"country": "US", "region": "other", "plan": "paid"}
}

print(f"Sending test request with user_id={query['user_id']}...\n")

response = requests.post(f"{API_BASE_URL}/chat", json=query, timeout=60)

if response.status_code == 200:
    data = response.json()
    logs = data.get('console_logs', [])
    
    print("📝 CONSOLE LOGS FROM API:\n")
    print("-" * 70)
    
    # Show all logs
    for log in logs:
        if 'TOKEN' in log or 'COST' in log or 'WARNING' in log or '⚠️' in log:
            print(log)
    
    print("-" * 70)
    
    # Analysis
    has_tokens = any('TOKEN TRACKING' in log for log in logs)
    has_costs = any('COST TRACKING' in log and 'SKIPPED' not in log for log in logs)
    
    model_missing = any('model_name is missing' in log for log in logs)
    user_missing = any('user_id is missing' in log for log in logs)
    cost_zero = any('cost is 0' in log for log in logs)
    
    print("\n📊 ANALYSIS:")
    print(f"  Tokens tracked: {'✅ YES' if has_tokens else '❌ NO'}")
    print(f"  Costs tracked: {'✅ YES' if has_costs else '❌ NO'}")
    
    if not has_costs:
        print("\n⚠️  COST NOT TRACKED. Reason:")
        if model_missing:
            print("  ❌ model_name is missing")
        elif user_missing:
            print("  ❌ user_id is missing")
        elif cost_zero:
            print("  ❌ cost is 0 (free model)")
        else:
            print("  ❓ Unknown - check logs above")
    
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)

