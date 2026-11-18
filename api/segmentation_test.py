#!/usr/bin/env python3
"""
Tutorial 2 Segmentation Test Script
Tests the geographic + business tier targeting matrix to ensure correct model and tool routing.
"""

import requests
from typing import Dict, Any

def test_user_scenario(user_context: Dict[str, Any], expected_config: Dict[str, Any]) -> Dict[str, Any]:
    """Test a specific user scenario and validate the configuration"""

    # Test query with PII to verify security agent behavior
    test_query = "My name is John Doe, email: john.doe@example.com. I'm a VP at StarSystems and need help with documentation research"

    payload = {
        "message": test_query,
        "user_id": user_context.get("user_id", "test-user"),
        "user_context": user_context
    }

    try:
        response = requests.post("http://localhost:8000/chat", json=payload, timeout=45)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"API Error: {response.status_code}: {response.text}",
                "user_context": user_context
            }

        result = response.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {e}",
            "user_context": user_context
        }

    # Extract actual configuration from response
    actual_config = {
        agent_config["agent_name"]: {
            "model": agent_config.get("model", "unknown"),
            "variation_key": agent_config.get("variation_key", "unknown"),
            "tools": agent_config.get("tools", []),
        }
        for agent_config in result.get("agent_configurations") or []
    }

    # Check for MCP tools specifically
    support_tools = actual_config.get("support-agent", {}).get("tools", [])
    has_mcp_tools = any(tool in support_tools for tool in ["arxiv_search", "openalex_search"])

    response_text = result.get("response", "")
    return {
        "success": True,
        "user_context": user_context,
        "expected": expected_config,
        "actual": actual_config,
        "has_mcp_tools": has_mcp_tools,
        "response_length": len(response_text),
        "tool_calls": result.get("tool_calls", []),
        "response": response_text[:200] + "..." if len(response_text) > 200 else response_text
    }

def validate_configuration(test_result: Dict[str, Any]) -> Dict[str, bool]:
    """Validate if the actual configuration matches expected"""

    if not test_result.get("success"):
        return {"overall": False, "error": test_result.get("error", "Unknown error")}

    support_actual = test_result["actual"].get("support-agent", {})
    support_expected = test_result["expected"].get("support_agent", {})

    validations = {}

    # Model validation
    actual_model = support_actual.get("model", "").lower()
    expected_model = support_expected.get("model", "").lower()
    validations["model_match"] = expected_model in actual_model or actual_model in expected_model

    # Variation validation
    validations["variation_match"] = support_actual.get("variation_key", "") == support_expected.get("variation_key", "")

    # Tools validation
    expected_tools = support_expected.get("tools", [])
    validations["tools_match"] = set(expected_tools).issubset(support_actual.get("tools", []))

    # MCP tools validation for paid users
    should_have_mcp = test_result["user_context"].get("plan") == "paid"
    validations["mcp_tools_correct"] = test_result["has_mcp_tools"] == should_have_mcp

    validations["overall"] = all(validations.values())
    return validations

def print_detailed_results(test_result: Dict[str, Any], validations: Dict[str, bool]):
    """Print detailed test results"""

    def status(check):
        return "✅" if validations.get(check) else "❌"

    user_ctx = test_result["user_context"]
    user_desc = f"{user_ctx['country']} {user_ctx['plan']} user"

    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {user_desc} (ID: {user_ctx['user_id']})")
    print(f"{'='*60}")

    if not test_result.get("success"):
        print(f"❌ TEST FAILED: {test_result.get('error', 'Unknown error')}")
        return

    support_actual = test_result["actual"].get("support-agent", {})
    support_expected = test_result["expected"].get("support_agent", {})

    # Support Agent Results
    print("📊 SUPPORT AGENT:")
    print(f"   Model: {support_actual.get('model', 'unknown')} (expected: {support_expected.get('model', 'unknown')}) {status('model_match')}")
    print(f"   Variation: {support_actual.get('variation_key', 'unknown')} (expected: {support_expected.get('variation_key', 'unknown')}) {status('variation_match')}")
    print(f"   Tools: {support_actual.get('tools', [])} {status('tools_match')}")
    print(f"   Expected: {support_expected.get('tools', [])}")

    should_have_mcp = user_ctx.get("plan") == "paid"
    print(f"   MCP Tools: {'Yes' if test_result['has_mcp_tools'] else 'No'} (should be: {'Yes' if should_have_mcp else 'No'}) {status('mcp_tools_correct')}")

    # Response info
    print("\n📝 RESPONSE:")
    print(f"   Length: {test_result['response_length']} chars")
    print(f"   Tools Called: {test_result['tool_calls']}")
    print(f"   Preview: {test_result['response'][:100]}...")

    # Overall result
    overall_status = "✅ PASSED" if validations.get("overall") else "❌ FAILED"
    print(f"\n🎯 RESULT: {overall_status}")

def main():
    """Run all segmentation tests"""
    print("🚀 COMPREHENSIVE TUTORIAL 2 SEGMENTATION TESTS")
    print("Testing Geographic + Business Tier Targeting Matrix")
    print("=" * 70)

    test_scenarios = [
        {
            "user_context": {"country": "DE", "plan": "paid", "user_id": "user_eu_paid_001", "region": "europe"},
            "expected_config": {
                "support_agent": {
                    "model": "claude-sonnet-5-5",
                    "variation_key": "eu-paid",
                    "tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "openalex_search"]
                }
            },
            "description": "EU Paid → Claude Sonnet + Full MCP Tools"
        },
        {
            "user_context": {"country": "DE", "plan": "free", "user_id": "user_eu_free_001", "region": "europe"},
            "expected_config": {
                "support_agent": {
                    "model": "claude-haiku-5-5",
                    "variation_key": "eu-free",
                    "tools": ["search_v1"]
                }
            },
            "description": "EU Free → Claude Haiku + Basic Tools"
        },
        {
            "user_context": {"country": "US", "plan": "paid", "user_id": "user_other_paid_001", "region": "other"},
            "expected_config": {
                "support_agent": {
                    "model": "gpt-6.2-sol",
                    "variation_key": "other-paid",
                    "tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "openalex_search"]
                }
            },
            "description": "US Paid → GPT-6.2 Sol + Full MCP Tools"
        },
        {
            "user_context": {"country": "US", "plan": "free", "user_id": "user_other_free_001", "region": "other"},
            "expected_config": {
                "support_agent": {
                    "model": "gpt-6-luna",
                    "variation_key": "other-free",
                    "tools": ["search_v1"]
                }
            },
            "description": "US Free → GPT-6 Luna + Basic Tools"
        }
    ]

    total_tests = len(test_scenarios)
    passed_tests = 0

    for scenario in test_scenarios:
        print(f"\n🔄 Running: {scenario['description']}")

        test_result = test_user_scenario(scenario["user_context"], scenario["expected_config"])
        validations = validate_configuration(test_result)
        print_detailed_results(test_result, validations)

        if validations.get("overall"):
            passed_tests += 1

    failed_tests = total_tests - passed_tests

    # Final Summary
    print("\n" + "=" * 70)
    print("📊 FINAL RESULTS")
    print("=" * 70)
    print(f"✅ PASSED: {passed_tests}/{total_tests}")
    print(f"❌ FAILED: {failed_tests}/{total_tests}")

    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! LaunchDarkly targeting is working correctly.")
        print("   • Geographic segmentation: Working")
        print("   • Business tier routing: Working")
        print("   • Model assignment: Working")
        print("   • Tool configuration: Working")
        print("   • MCP integration: Working")
    else:
        print(f"\n⚠️  {failed_tests} TEST(S) FAILED - LaunchDarkly configuration needs attention.")
        print("   1. Check segment rules in LaunchDarkly dashboard")
        print("   2. Verify targeting rules for support-agent AI config")
        print("   3. Ensure segments are properly matching user contexts")
        print("   4. Wait a few minutes for LaunchDarkly propagation")

    print("\n🔗 Next: Test manually in UI at http://localhost:8501")

if __name__ == "__main__":
    main()
