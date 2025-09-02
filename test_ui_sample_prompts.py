#!/usr/bin/env python3
"""
Test script for the 5 UI sample prompts to validate:
1. Correct tools are called
2. Final response uses the results of these tools
"""

import asyncio
import requests
import json
import time
from typing import Dict, List, Any

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test_user_ui_validation"

# The 5 UI sample prompts with expected tool usage
SAMPLE_PROMPTS = [
    {
        "name": "Internal Knowledge",
        "query": "What information do you have about machine learning in your knowledge base?",
        "expected_tools": [],  # Should use model's knowledge, no tools needed
        "expected_content_keywords": ["machine learning", "knowledge"],
        "description": "Tests model's internal knowledge without tools"
    },
    {
        "name": "ArXiv Research", 
        "query": "Find recent ArXiv papers on reinforcement learning from the last 6 months",
        "expected_tools": ["arxiv_search", "search_papers"],  # MCP ArXiv tools
        "expected_content_keywords": ["reinforcement learning", "arxiv", "papers", "recent"],
        "description": "Tests MCP ArXiv integration"
    },
    {
        "name": "Academic Search",
        "query": "Search Semantic Scholar for papers on federated learning", 
        "expected_tools": ["semantic_scholar", "search_semantic_scholar"],  # MCP Semantic Scholar tools
        "expected_content_keywords": ["federated learning", "semantic scholar", "papers"],
        "description": "Tests MCP Semantic Scholar integration"
    },
    {
        "name": "RAG + Reranking",
        "query": "Find the best matches for 'deep learning algorithms' in your documentation",
        "expected_tools": ["search_v2", "reranking"],  # Internal RAG tools
        "expected_content_keywords": ["deep learning algorithms", "documentation", "matches"],
        "description": "Tests internal RAG + reranking pipeline"
    },
    {
        "name": "Full Stack Search", 
        "query": "Compare what you know about transformers from your knowledge base with recent ArXiv and Semantic Scholar papers",
        "expected_tools": ["search_v2", "arxiv_search", "semantic_scholar"],  # All tools combined
        "expected_content_keywords": ["transformers", "knowledge base", "arxiv", "semantic scholar", "compare"],
        "description": "Tests full multi-source search integration"
    }
]

def send_chat_request(query: str, user_id: str = TEST_USER_ID) -> Dict[str, Any]:
    """Send a chat request to the API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "user_id": user_id,
                "message": query
            },
            timeout=60  # 1 minute timeout
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"HTTP {response.status_code}: {response.text}",
                "success": False
            }
            
    except Exception as e:
        return {
            "error": f"Request failed: {str(e)}",
            "success": False
        }

def validate_tool_usage(actual_tools: List[str], expected_tools: List[str], prompt_name: str) -> Dict[str, Any]:
    """Validate that the correct tools were used"""
    results = {
        "passed": False,
        "details": [],
        "score": 0
    }
    
    # Convert to lowercase for comparison
    actual_tools_lower = [tool.lower() for tool in actual_tools]
    expected_tools_lower = [tool.lower() for tool in expected_tools]
    
    if not expected_tools:
        # No tools expected - should be model-only response
        if not actual_tools:
            results["passed"] = True
            results["score"] = 100
            results["details"].append("✅ Correctly used no tools (model knowledge only)")
        else:
            results["details"].append(f"❌ Expected no tools but used: {actual_tools}")
    else:
        # Check if any expected tools were used
        tools_found = []
        for expected_tool in expected_tools_lower:
            for actual_tool in actual_tools_lower:
                if expected_tool in actual_tool or actual_tool in expected_tool:
                    tools_found.append(actual_tool)
                    break
        
        if tools_found:
            results["passed"] = True
            results["score"] = int((len(tools_found) / len(expected_tools)) * 100)
            results["details"].append(f"✅ Found expected tools: {tools_found}")
            
            # Check for unexpected tools
            unexpected_tools = [t for t in actual_tools_lower if not any(exp in t or t in exp for exp in expected_tools_lower)]
            if unexpected_tools:
                results["details"].append(f"ℹ️  Additional tools used: {unexpected_tools}")
        else:
            results["details"].append(f"❌ Expected tools {expected_tools} but got {actual_tools}")
    
    return results

def validate_content_usage(response_text: str, keywords: List[str], tools_used: List[str]) -> Dict[str, Any]:
    """Validate that the response uses content from the tools"""
    results = {
        "passed": False,
        "details": [],
        "score": 0
    }
    
    response_lower = response_text.lower()
    
    # Check for expected keywords
    keywords_found = []
    for keyword in keywords:
        if keyword.lower() in response_lower:
            keywords_found.append(keyword)
    
    keyword_score = int((len(keywords_found) / len(keywords)) * 100) if keywords else 100
    
    # Check for tool result integration
    tool_integration_score = 0
    integration_signals = []
    
    if tools_used:
        # Look for signals that tool results were integrated
        integration_indicators = [
            "based on", "according to", "found", "search results", "papers show",
            "research indicates", "studies suggest", "documentation shows",
            "arxiv", "semantic scholar", "references", "citations"
        ]
        
        for indicator in integration_indicators:
            if indicator in response_lower:
                integration_signals.append(indicator)
        
        if integration_signals:
            tool_integration_score = 100
            results["details"].append(f"✅ Tool results integrated (signals: {integration_signals[:3]})")
        else:
            results["details"].append("❌ No clear evidence of tool result integration")
    else:
        tool_integration_score = 100  # No tools expected
    
    # Overall content validation
    if keywords_found:
        results["details"].append(f"✅ Keywords found: {keywords_found}")
    else:
        results["details"].append(f"❌ No expected keywords found: {keywords}")
    
    results["score"] = int((keyword_score + tool_integration_score) / 2)
    results["passed"] = results["score"] >= 70  # 70% threshold
    
    return results

def run_test(prompt_info: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single prompt test"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {prompt_info['name']}")
    print(f"📝 Query: {prompt_info['query']}")
    print(f"🔧 Expected tools: {prompt_info['expected_tools']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Send the request
    result = send_chat_request(prompt_info['query'])
    
    end_time = time.time()
    duration = end_time - start_time
    
    test_result = {
        "prompt_name": prompt_info['name'],
        "query": prompt_info['query'],
        "duration_seconds": duration,
        "success": False,
        "tool_validation": {},
        "content_validation": {},
        "response_length": 0,
        "tools_used": [],
        "error": None
    }
    
    if "error" in result:
        test_result["error"] = result["error"]
        print(f"❌ REQUEST FAILED: {result['error']}")
        return test_result
    
    # Extract response details
    response_text = result.get("response", "")
    tools_used = result.get("tool_calls", [])
    
    test_result["response_length"] = len(response_text)
    test_result["tools_used"] = tools_used
    
    print(f"⏱️  Duration: {duration:.1f}s")
    print(f"📊 Response length: {len(response_text)} chars")
    print(f"🔧 Tools used: {tools_used}")
    
    # Validate tool usage
    tool_validation = validate_tool_usage(
        tools_used, 
        prompt_info['expected_tools'], 
        prompt_info['name']
    )
    test_result["tool_validation"] = tool_validation
    
    print(f"\n🔧 TOOL VALIDATION:")
    for detail in tool_validation["details"]:
        print(f"   {detail}")
    print(f"   Score: {tool_validation['score']}/100")
    
    # Validate content usage
    content_validation = validate_content_usage(
        response_text,
        prompt_info['expected_content_keywords'],
        tools_used
    )
    test_result["content_validation"] = content_validation
    
    print(f"\n📝 CONTENT VALIDATION:")
    for detail in content_validation["details"]:
        print(f"   {detail}")
    print(f"   Score: {content_validation['score']}/100")
    
    # Overall success
    test_result["success"] = (
        tool_validation["passed"] and 
        content_validation["passed"] and
        len(response_text) > 50  # Reasonable response length
    )
    
    if test_result["success"]:
        print(f"\n✅ TEST PASSED")
    else:
        print(f"\n❌ TEST FAILED")
        
    # Show response preview
    preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
    print(f"\n📄 Response preview: {preview}")
    
    return test_result

def main():
    """Run all UI sample prompt tests"""
    print("🚀 UI Sample Prompts Test Suite")
    print("="*60)
    
    # Check if API is running by making a simple chat request
    try:
        test_response = send_chat_request("hello")
        if "error" in test_response:
            print(f"❌ Cannot connect to API at {API_BASE_URL}: {test_response['error']}")
            print("Make sure the backend is running: uv run uvicorn api.main:app --reload --port 8001")
            return
    except Exception as e:
        print(f"❌ Cannot connect to API at {API_BASE_URL}: {e}")
        print("Make sure the backend is running: uv run uvicorn api.main:app --reload --port 8001")
        return
    
    print(f"✅ API is running at {API_BASE_URL}")
    
    all_results = []
    
    # Run each test
    for prompt_info in SAMPLE_PROMPTS:
        result = run_test(prompt_info)
        all_results.append(result)
        time.sleep(1)  # Brief pause between tests
    
    # Summary report
    print(f"\n{'='*60}")
    print("📊 SUMMARY REPORT")
    print(f"{'='*60}")
    
    passed_tests = [r for r in all_results if r["success"]]
    failed_tests = [r for r in all_results if not r["success"]]
    
    print(f"✅ Passed: {len(passed_tests)}/{len(all_results)}")
    print(f"❌ Failed: {len(failed_tests)}/{len(all_results)}")
    
    if failed_tests:
        print(f"\nFailed tests:")
        for test in failed_tests:
            error_msg = test.get("error", "Validation failed")
            print(f"  • {test['prompt_name']}: {error_msg}")
    
    # Detailed results table
    print(f"\n📈 DETAILED RESULTS:")
    print(f"{'Test Name':<20} {'Tools':<8} {'Content':<8} {'Duration':<8} {'Status'}")
    print("-" * 60)
    
    for result in all_results:
        tool_score = result.get("tool_validation", {}).get("score", 0)
        content_score = result.get("content_validation", {}).get("score", 0)
        duration = f"{result['duration_seconds']:.1f}s"
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        
        print(f"{result['prompt_name']:<20} {tool_score:<8} {content_score:<8} {duration:<8} {status}")
    
    # Save detailed results
    output_file = "ui_sample_prompts_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    return len(passed_tests) == len(all_results)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)