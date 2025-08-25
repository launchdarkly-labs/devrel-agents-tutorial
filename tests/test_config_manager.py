#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from policy.config_manager import ConfigManager

async def test_config_manager():
    print("Testing ConfigManager with no defaults/fallbacks...")
    
    # Check if LD_SDK_KEY is set
    ld_sdk_key = os.getenv('LD_SDK_KEY')
    if not ld_sdk_key:
        print("❌ LD_SDK_KEY not set - this should fail during ConfigManager init")
        try:
            config_manager = ConfigManager()
            print("❌ ERROR: ConfigManager should have failed without LD_SDK_KEY")
        except ValueError as e:
            print(f"✅ PASS: ConfigManager correctly failed: {e}")
        return
    
    print(f"✅ LD_SDK_KEY is set: {ld_sdk_key[:10]}...")
    
    try:
        config_manager = ConfigManager()
        print("✅ ConfigManager initialized successfully")
        
        # Test getting config for a user
        print("\nTesting get_config...")
        config = await config_manager.get_config("test-user-123")
        
        print("✅ Configuration retrieved successfully:")
        print(f"  - Variation: {config.variation_key}")
        print(f"  - Model: {config.model}")
        print(f"  - Instructions: {config.instructions[:50]}...")
        print(f"  - Allowed Tools: {config.allowed_tools}")
        print(f"  - Max Tool Calls: {config.max_tool_calls}")
        print(f"  - Max Cost: {config.max_cost}")
        print(f"  - Workflow Type: {config.workflow_type}")
        
    except ValueError as e:
        print(f"❌ Configuration error (this is expected if LaunchDarkly flags aren't set up): {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_config_manager())