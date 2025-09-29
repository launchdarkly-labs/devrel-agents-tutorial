#!/usr/bin/env python3
"""
Tutorial 2 Segmentation Test Script
Tests the geographic + business tier targeting matrix to ensure correct model and tool routing.
"""

import requests
import json
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
                "error": f"API Error: {response.status_code}",
                "details": response.text
            }
            
        result = response.json()
        
        # Extract actual configuration from response
        actual_config = {
            "support-agent": {},
            "security-agent": {},
            "supervisor-agent": {}
        }
        
        # Parse agent configurations from response
        agent_configs = result.get("agent_configurations", [])
        for agent_config in agent_configs:
            agent_name = agent_config.get("agent_name", "unknown")
            if agent_name in actual_config:
                actual_config[agent_name] = {
                    "model": agent_config.get("model", "unknown"),
                    "variation_key": agent_config.get("variation_key", "unknown"),
                    "tools": agent_config.get("tools", []),
                    "tool_details": agent_config.get("tool_details", [])
                }
        
        # Check for MCP tools specifically
        support_tools = actual_config.get("support-agent", {}).get("tools", [])
        has_mcp_tools = any(tool in support_tools for tool in ["arxiv_search", "semantic_scholar"])

        # Check security agent redaction behavior
        response_text = result.get("response", "")
        redacted_text = result.get("redacted_text", "")

        # Check if PII was properly redacted (should not contain original PII in final response)
        pii_properly_redacted = (
            "John Doe" not in response_text and
            "john.doe@example.com" not in response_text and
            "[REDACTED]" in redacted_text  # Should have redacted text in workflow
        )

        # For EU users, check if job title and company were redacted (strict security)
        strict_redaction_working = True
        if user_context.get("country") in ["DE", "FR", "ES", "IT"]:  # EU countries
            strict_redaction_working = (
                "VP" not in redacted_text and
                "StarSystems" not in redacted_text and
                "[REDACTED]" in redacted_text
            )

        return {
            "success": True,
            "user_context": user_context,
            "expected": expected_config,
            "actual": actual_config,
            "has_mcp_tools": has_mcp_tools,
            "pii_properly_redacted": pii_properly_redacted,
            "strict_redaction_working": strict_redaction_working,
            "redacted_text": redacted_text,
            "response_length": len(result.get("response", "")),
            "tool_calls": result.get("tool_calls", []),
            "response": result.get("response", "")[:200] + "..." if len(result.get("response", "")) > 200 else result.get("response", "")
        }
            
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {e}",
            "user_context": user_context
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON decode error: {e}",
            "user_context": user_context
        }

def validate_configuration(test_result: Dict[str, Any]) -> Dict[str, bool]:
    """Validate if the actual configuration matches expected"""
    
    if not test_result.get("success"):
        return {"overall": False, "error": test_result.get("error", "Unknown error")}
    
    expected = test_result["expected"]
    actual = test_result["actual"]
    user_context = test_result["user_context"]
    
    validations = {}
    
    # Check support agent configuration
    support_actual = actual.get("support-agent", {})
    support_expected = expected.get("support_agent", {})
    
    # Model validation
    actual_model = support_actual.get("model", "").lower()
    expected_model = support_expected.get("model", "").lower()
    validations["model_match"] = expected_model in actual_model or actual_model in expected_model
    
    # Variation validation  
    actual_variation = support_actual.get("variation_key", "")
    expected_variation = support_expected.get("variation_key", "")
    validations["variation_match"] = actual_variation == expected_variation
    
    # Tools validation
    actual_tools = support_actual.get("tools", [])
    expected_tools = support_expected.get("tools", [])
    validations["tools_match"] = set(expected_tools).issubset(set(actual_tools)) if expected_tools else True
    
    # MCP tools validation for paid users
    has_mcp = test_result.get("has_mcp_tools", False)
    should_have_mcp = user_context.get("plan") == "paid"
    validations["mcp_tools_correct"] = has_mcp == should_have_mcp
    
    # Overall validation
    validations["overall"] = all([
        validations.get("model_match", False),
        validations.get("variation_match", False), 
        validations.get("tools_match", False),
        validations.get("mcp_tools_correct", False)
    ])
    
    return validations

def print_detailed_results(test_result: Dict[str, Any], validations: Dict[str, bool]):
    """Print detailed test results"""
    
    user_ctx = test_result["user_context"]
    user_desc = f"{user_ctx['country']} {user_ctx['plan']} user"
    
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {user_desc} (ID: {user_ctx['user_id']})")
    print(f"{'='*60}")
    
    if not test_result.get("success"):
        print(f" TEST FAILED: {test_result.get('error', 'Unknown error')}")
        return
    
    expected = test_result["expected"]
    actual = test_result["actual"]
    
    # Support Agent Results
    print(f" SUPPORT AGENT:")
    support_actual = actual.get("support-agent", {})
    support_expected = expected.get("support_agent", {})
    
    # Model comparison
    actual_model = support_actual.get("model", "unknown")
    expected_model = support_expected.get("model", "unknown")
    model_status = "" if validations.get("model_match") else ""
    print(f"   Model: {actual_model} (expected: {expected_model}) {model_status}")
    
    # Variation comparison
    actual_variation = support_actual.get("variation_key", "unknown")
    expected_variation = support_expected.get("variation_key", "unknown")
    variation_status = "" if validations.get("variation_match") else ""
    print(f"   Variation: {actual_variation} (expected: {expected_variation}) {variation_status}")
    
    # Tools comparison
    actual_tools = support_actual.get("tools", [])
    expected_tools = support_expected.get("tools", [])
    tools_status = "" if validations.get("tools_match") else ""
    print(f"   Tools: {actual_tools} {tools_status}")
    print(f"   Expected: {expected_tools}")
    
    # MCP tools check
    has_mcp = test_result.get("has_mcp_tools", False)
    should_have_mcp = user_ctx.get("plan") == "paid"
    mcp_status = "" if validations.get("mcp_tools_correct") else ""
    print(f"   MCP Tools: {'Yes' if has_mcp else 'No'} (should be: {'Yes' if should_have_mcp else 'No'}) {mcp_status}")
    
    # Response info
    print(f" RESPONSE:")
    print(f"   Length: {test_result.get('response_length', 0)} chars")
    print(f"   Tools Called: {test_result.get('tool_calls', [])}")
    print(f"   Preview: {test_result.get('response', 'No response')[:100]}...")
    
    # Overall result
    overall_status = " PASSED" if validations.get("overall") else " FAILED"
    print(f"\n RESULT: {overall_status}")

def main():
    """Run all segmentation tests"""
    print(" COMPREHENSIVE TUTORIAL 2 SEGMENTATION TESTS")
    print("Testing Geographic + Business Tier Targeting Matrix")
    print("=" * 70)
    
    test_scenarios = [
        {
            "user_context": {"country": "DE", "plan": "paid", "user_id": "user_eu_paid_001", "region": "europe"},
            "expected_config": {
                "support_agent": {
                    "model": "claude-3-7-sonnet-latest",
                    "variation_key": "eu-paid",
                    "tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]
                }
            },
            "description": "EU Paid → Claude Sonnet + Full MCP Tools"
        },
        {
            "user_context": {"country": "DE", "plan": "free", "user_id": "user_eu_free_001", "region": "europe"},
            "expected_config": {
                "support_agent": {
                    "model": "claude-3-5-haiku-20241022",
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
                    "model": "chatgpt-4o-latest",
                    "variation_key": "other-paid",
                    "tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]
                }
            },
            "description": "US Paid → GPT-4 + Full MCP Tools"
        },
        {
            "user_context": {"country": "US", "plan": "free", "user_id": "user_other_free_001", "region": "other"},
            "expected_config": {
                "support_agent": {
                    "model": "gpt-4o-mini-2024-07-18",
                    "variation_key": "other-free",
                    "tools": ["search_v1"]
                }
            },
            "description": "US Free → GPT-4o Mini + Basic Tools"
        }
    ]
    
    passed_tests = 0
    failed_tests = 0
    total_tests = len(test_scenarios)
    
    for scenario in test_scenarios:
        print(f"\n🔄 Running: {scenario['description']}")
        
        test_result = test_user_scenario(
            scenario["user_context"],
            scenario["expected_config"]
        )
        
        validations = validate_configuration(test_result)
        print_detailed_results(test_result, validations)
        
        if validations.get("overall"):
            passed_tests += 1
        else:
            failed_tests += 1
    
    # Final Summary
    print("\n" + "=" * 70)
    print(f" FINAL RESULTS")
    print(f"=" * 70)
    print(f" PASSED: {passed_tests}/{total_tests}")
    print(f" FAILED: {failed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print(f"\n🎉 ALL TESTS PASSED! LaunchDarkly targeting is working correctly.")
        print(f"   • Geographic segmentation: Working")
        print(f"   • Business tier routing: Working") 
        print(f"   • Model assignment: Working")
        print(f"   • Tool configuration: Working")
        print(f"   • MCP integration: Working")
    else:
        print(f"\n  {failed_tests} TEST(S) FAILED - LaunchDarkly configuration needs attention.")
        print(f"   1. Check segment rules in LaunchDarkly dashboard")
        print(f"   2. Verify targeting rules for support-agent AI config")
        print(f"   3. Ensure segments are properly matching user contexts")
        print(f"   4. Wait a few minutes for LaunchDarkly propagation")
        
    print(f"\n🔗 Next: Test manually in UI at http://localhost:8501")

if __name__ == "__main__":
    main()