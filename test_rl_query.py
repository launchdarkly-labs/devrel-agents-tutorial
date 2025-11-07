#!/usr/bin/env python3
"""Quick test to verify RL knowledge base queries work"""

import requests
import json

API_URL = "http://localhost:8000"

# Test query from new test data
query = "What is a Markov Decision Process and why is it important in reinforcement learning?"

print(f"Testing RL query: {query}\n")

try:
    response = requests.post(
        f"{API_URL}/chat",
        json={
            "message": query,
            "user_id": "test_user",
            "user_context": {"country": "US", "plan": "paid"}
        },
        timeout=30
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"\nResponse: {data['response'][:500]}...")
        print(f"\nVariation: {data.get('variation_key')}")
        print(f"Model: {data.get('model')}")

        # Check if response mentions RL concepts
        response_lower = data['response'].lower()
        rl_terms = ['markov', 'mdp', 'state', 'action', 'reward', 'reinforcement']
        found_terms = [term for term in rl_terms if term in response_lower]

        print(f"\nRL terms found: {found_terms}")

        if len(found_terms) >= 3:
            print("✅ Response appears to be about RL!")
        else:
            print("⚠️  Response may not be about RL")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
