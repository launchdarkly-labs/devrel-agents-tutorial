#!/usr/bin/env python3
"""
Send a few requests and capture console logs to see why costs are being skipped
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = f"http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}"

def analyze_logs():
    print("🔍 Sending test requests to capture cost tracking logs...\n")
    print("=" * 70)
    
    test_queries = [
        {"user_id": f"log_test_user_{i}", 
         "message": "What is machine learning?",
         "user_context": {"country": "US", "region": "other", "plan": "paid"}}
        for i in range(5)
    ]
    
    cost_skipped_reasons = {
        "model_name_missing": 0,
        "user_id_missing": 0,
        "cost_is_zero": 0,
        "cost_tracked": 0,
        "token_only": 0
    }
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/5] Testing request...")
        
        try:
            response = requests.post(f"{API_BASE_URL}/chat", json=query, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                logs = data.get('console_logs', [])
                
                has_tokens = False
                has_costs = False
                skip_reason = None
                
                for log in logs:
                    if 'TOKEN TRACKING' in log:
                        has_tokens = True
                        print(f"  ✅ {log}")
                    elif 'COST TRACKING' in log and 'SKIPPED' not in log:
                        has_costs = True
                        print(f"  💰 {log}")
                    elif 'COST SKIPPED' in log:
                        print(f"  ⚠️  {log}")
                        if 'model_name is missing' in log:
                            skip_reason = "model_name_missing"
                        elif 'user_id is missing' in log:
                            skip_reason = "user_id_missing"
                        elif 'cost is 0' in log:
                            skip_reason = "cost_is_zero"
                
                # Categorize
                if has_costs:
                    cost_skipped_reasons["cost_tracked"] += 1
                elif skip_reason:
                    cost_skipped_reasons[skip_reason] += 1
                elif has_tokens:
                    cost_skipped_reasons["token_only"] += 1
                    print(f"  ⚠️  MYSTERY: Tokens tracked but no cost tracking or skip message!")
                    
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("\n📊 ANALYSIS OF 5 TEST REQUESTS:\n")
    print(f"Cost tracked successfully: {cost_skipped_reasons['cost_tracked']}/5")
    print(f"Skipped - model_name missing: {cost_skipped_reasons['model_name_missing']}/5")
    print(f"Skipped - user_id missing: {cost_skipped_reasons['user_id_missing']}/5")
    print(f"Skipped - cost is 0: {cost_skipped_reasons['cost_is_zero']}/5")
    print(f"Tokens but no cost (mystery): {cost_skipped_reasons['token_only']}/5")
    
    print("\n" + "=" * 70)
    
    if cost_skipped_reasons["model_name_missing"] > 0:
        print("\n⚠️  ISSUE: model_name is not being passed to track_metrics_async!")
    elif cost_skipped_reasons["user_id_missing"] > 0:
        print("\n⚠️  ISSUE: user_id is not being passed to track_metrics_async!")
    elif cost_skipped_reasons["cost_is_zero"] > 0:
        print("\n⚠️  ISSUE: Free models (like Mistral) are being used!")
    elif cost_skipped_reasons["token_only"] > 0:
        print("\n⚠️  MYSTERY: Tokens tracked but cost tracking silently skipped!")
        print("   This suggests an exception or logic bug in the cost tracking code.")
    elif cost_skipped_reasons["cost_tracked"] == 5:
        print("\n✅ All requests successfully tracked costs!")
        print("   The issue must be with earlier requests in your experiment.")

if __name__ == "__main__":
    analyze_logs()

