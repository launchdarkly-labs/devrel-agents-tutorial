#!/usr/bin/env python3
"""Test script to diagnose evaluator issues in CI"""
import sys
import asyncio

sys.path.insert(0, '.')

async def main():
    try:
        from evaluators.local_evaluator import AgentsDemoEvaluator
        print("✅ Evaluator imported successfully")
        
        evaluator = AgentsDemoEvaluator()
        print(f"✅ Evaluator instantiated: {evaluator.api_url}")
        
        # Test a simple call
        result = await evaluator.evaluate_case(
            config_key="test",
            test_input="hello",
            context_attributes={"test": "value"}
        )
        print(f"✅ Evaluator call completed: error={result.error is not None}, response_len={len(result.response)}")
        if result.error:
            print(f"   Error details: {result.error[:500]}")
        
        await evaluator.cleanup()
        
    except Exception as e:
        import traceback
        print(f"❌ Evaluator test FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

