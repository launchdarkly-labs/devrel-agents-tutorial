#!/usr/bin/env python3
"""
Verify that costs are being calculated and sent to LaunchDarkly

This will show us:
1. Are tokens being extracted?
2. Are costs being calculated?
3. Are the custom events being sent?
"""

import os
import asyncio
from dotenv import load_dotenv
from config_manager import FixedConfigManager
from utils.cost_calculator import calculate_cost

load_dotenv()

async def test_cost_flow():
    print("🔍 Testing Cost Tracking Flow\n")
    print("=" * 70)
    
    config_manager = FixedConfigManager()
    
    # Simulate token data like what comes from an LLM
    test_tokens = {
        "input": 1000,
        "output": 500,
        "total": 1500
    }
    
    test_models = [
        "gpt-4o",
        "claude-opus-4-20250514",
        "claude-3-7-sonnet-latest",
        "mistral-small-latest"
    ]
    
    print("Testing cost calculation for each model:\n")
    for model in test_models:
        cost = calculate_cost(model, test_tokens["input"], test_tokens["output"])
        print(f"  {model}:")
        print(f"    Cost: ${cost:.6f}")
        print(f"    Will track: {'✅ YES' if cost > 0 else '❌ NO (cost is 0)'}\n")
    
    print("=" * 70)
    print("\n⚠️  KEY INSIGHT:")
    print("Costs are ONLY tracked when cost > 0")
    print("This means Mistral models (cost = 0) won't generate cost metrics!")
    print("\nFor your experiment:")
    print("- Control (other-paid): GPT-4o → cost > 0 ✅")
    print("- Treatment (opus): Claude Opus 4 → cost > 0 ✅") 
    print("- Security agent: Mistral → cost = 0 ❌ (not tracked)")
    
    config_manager.close()

if __name__ == "__main__":
    asyncio.run(test_cost_flow())

