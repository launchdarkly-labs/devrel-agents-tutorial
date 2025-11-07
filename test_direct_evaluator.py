#!/usr/bin/env python3
"""
Quick test of Direct evaluator with tools.py
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_direct_evaluator():
    # Import from the CI/CD package
    try:
        from ld_aic_cicd.evaluators.direct import DirectEvaluator
    except ImportError:
        print("❌ ld-aic-cicd package not installed")
        print("Install with: uv pip install git+https://...@feature/user-friendly-setup")
        return
    
    print("✅ DirectEvaluator imported successfully")
    
    # Initialize evaluator
    try:
        evaluator = DirectEvaluator()
        print(f"✅ DirectEvaluator initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    # Test with support-agent config
    print("\n🧪 Testing support-agent with tools...")
    result = await evaluator.evaluate_case(
        config_key="support-agent",
        test_input="What is LaunchDarkly?",
        context_attributes={
            "key": "test-user",
            "country": "US",
            "plan": "free"
        }
    )
    
    print(f"\n📊 Result:")
    print(f"  Variation: {result.variation}")
    print(f"  Latency: {result.latency_ms:.0f}ms")
    print(f"  Error: {result.error}")
    print(f"  Response preview: {result.response[:200]}...")
    
    await evaluator.cleanup()

if __name__ == "__main__":
    asyncio.run(test_direct_evaluator())
