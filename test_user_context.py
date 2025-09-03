#!/usr/bin/env python3
"""
Quick test to verify user context flow works with LaunchDarkly targeting
"""
import json
import sys
import os
from pathlib import Path

# Add the project root to path so we can import modules
sys.path.append(str(Path(__file__).parent))

async def test_user_context():
    """Test that user context attributes are properly handled"""
    
    print("🔍 Testing user context flow...")
    
    # Test 1: Load sample users
    try:
        with open('data/fake_users.json', 'r') as f:
            users_data = json.load(f)
        print(f"✅ Loaded {len(users_data['users'])} sample users")
        
        # Verify we have all expected user types
        plans = set(user['plan'] for user in users_data['users'])
        countries = set(user['country'] for user in users_data['users'])
        regions = set(user['region'] for user in users_data['users'])
        
        expected_plans = {'free', 'basic', 'pro', 'enterprise'}
        expected_countries = {'US', 'DE', 'CA', 'FR', 'GB', 'JP', 'SG', 'AU'}
        expected_regions = {'north_america', 'europe', 'asia_pacific', 'general', 'healthcare'}
        
        print(f"✅ Plans covered: {plans} (expected: {expected_plans})")
        print(f"✅ Countries covered: {countries}")
        print(f"✅ Regions covered: {regions} (expected: {expected_regions})")
        
        if not expected_plans.issubset(plans):
            print(f"❌ Missing plans: {expected_plans - plans}")
            return False
        
        if not expected_regions.issubset(regions):
            print(f"❌ Missing regions: {expected_regions - regions}")
            return False
            
    except Exception as e:
        print(f"❌ Error loading sample users: {e}")
        return False
    
    # Test 2: Verify ConfigManager can handle user context
    try:
        from config_manager import FixedConfigManager
        
        # Don't actually initialize (requires LD SDK key)
        print("✅ ConfigManager import successful")
        
        # Check the user context mapping code
        import inspect
        source = inspect.getsource(FixedConfigManager.get_ai_config_with_tracker)
        
        # Verify it handles the expected attributes
        expected_attrs = ['country', 'plan', 'region']
        for attr in expected_attrs:
            if f"'{attr}'" in source:
                print(f"✅ ConfigManager handles '{attr}' attribute")
            else:
                print(f"❌ ConfigManager missing '{attr}' attribute handling")
                return False
        
    except Exception as e:
        print(f"❌ Error checking ConfigManager: {e}")
        return False
    
    # Test 3: Verify traffic generator sends correct context
    try:
        with open('tools/traffic_generator.py', 'r') as f:
            traffic_source = f.read()
        
        # Check that it sends the right user context structure
        if '"country": user["country"]' in traffic_source:
            print("✅ Traffic generator sends country")
        else:
            print("❌ Traffic generator missing country")
            return False
            
        if '"plan": user["plan"]' in traffic_source:
            print("✅ Traffic generator sends plan")
        else:
            print("❌ Traffic generator missing plan")
            return False
            
        if '"region": user["region"]' in traffic_source:
            print("✅ Traffic generator sends region")
        else:
            print("❌ Traffic generator missing region")
            return False
        
        # Check API URL
        if 'localhost:8001' in traffic_source:
            print("✅ Traffic generator uses correct API URL (8001)")
        else:
            print("❌ Traffic generator uses wrong API URL")
            return False
            
    except Exception as e:
        print(f"❌ Error checking traffic generator: {e}")
        return False
    
    print("\n✅ All user context tests passed!")
    print("\n🎯 Ready for testing:")
    print("1. Start API: uv run uvicorn api.main:app --reload --port 8001")
    print("2. Test traffic: python tools/traffic_generator.py --queries 10 --delay 1")
    print("3. Check LaunchDarkly dashboard for targeting results")
    
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_user_context())