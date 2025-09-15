#!/usr/bin/env python3
"""
Tutorial 2 Segmentation Test Script
Tests the geographic + business tier targeting matrix to ensure correct model and tool routing.
"""

import requests
import json
from typing import Dict, Any

def test_user_scenario(user_context: Dict[str, Any], expected_model: str, expected_tools: list = None) -> bool:
    """Test a specific user scenario and validate the response"""
    
    # Test query for research capabilities
    test_query = "Search for machine learning papers about reinforcement learning"
    
    payload = {
        "message": test_query,
        "user_id": user_context.get("user_id", "test-user"),
        "user_context": user_context
    }
    
    try:
        response = requests.post("http://localhost:8000/chat", json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return False
            
        result = response.json()
        
        # Print test results
        user_desc = f"{user_context.get('country', 'Unknown')} {user_context.get('plan', 'Unknown')}"
        print(f"\n🧪 Testing: {user_desc}")
        print(f"   Expected Model: {expected_model}")
        
        if expected_tools:
            print(f"   Expected Tools: {', '.join(expected_tools)}")
        
        # Check if we got a valid response
        if "response" in result:
            print(f"   ✅ Got response: {result['response'][:100]}...")
            return True
        else:
            print(f"   ❌ No response in result: {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return False

def main():
    """Run all segmentation tests"""
    print("🚀 Starting Tutorial 2 Segmentation Tests")
    print("Testing Geographic + Business Tier Matrix")
    print("=" * 50)
    
    test_scenarios = [
        {
            "user_context": {"country": "DE", "plan": "paid", "user_id": "eu-paid-user"},
            "expected_model": "claude-3-5-sonnet",
            "expected_tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"],
            "description": "EU Paid → Claude Sonnet + Full MCP tools"
        },
        {
            "user_context": {"country": "DE", "plan": "free", "user_id": "eu-free-user"},
            "expected_model": "claude-3-5-haiku",
            "expected_tools": ["search_v1"],
            "description": "EU Free → Claude Haiku + Basic tools"
        },
        {
            "user_context": {"country": "US", "plan": "paid", "user_id": "us-paid-user"},
            "expected_model": "gpt-4o",
            "expected_tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"],
            "description": "Other Paid → GPT-4 + Full MCP tools"
        },
        {
            "user_context": {"country": "US", "plan": "free", "user_id": "us-free-user"},
            "expected_model": "gpt-4o-mini",
            "expected_tools": ["search_v1"],
            "description": "Other Free → GPT-4o Mini + Basic tools"
        }
    ]
    
    passed_tests = 0
    total_tests = len(test_scenarios)
    
    for scenario in test_scenarios:
        print(f"\n📋 {scenario['description']}")
        
        success = test_user_scenario(
            scenario["user_context"],
            scenario["expected_model"],
            scenario["expected_tools"]
        )
        
        if success:
            passed_tests += 1
            print("   ✅ PASSED")
        else:
            print("   ❌ FAILED")
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("✅ All segmentation tests PASSED! Your targeting matrix is working correctly.")
    else:
        print("❌ Some tests FAILED. Check your LaunchDarkly configurations and targeting rules.")
        
    print("\n🔍 Next Steps:")
    print("   1. Check LaunchDarkly dashboard for segment matching")
    print("   2. Verify AI Config variations are properly targeted")
    print("   3. Test in the chat UI at http://localhost:8501")

if __name__ == "__main__":
    main()