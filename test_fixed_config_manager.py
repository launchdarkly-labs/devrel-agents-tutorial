#!/usr/bin/env python3
"""
Test the fixed ConfigManager to ensure it works like the direct test
"""
import asyncio
from fixed_config_manager import FixedConfigManager

async def test_fixed_config_manager():
    print("🧪 Testing Fixed ConfigManager...")
    
    try:
        # Initialize using the working pattern
        config_manager = FixedConfigManager()
        
        # Test getting config with tracker
        config = await config_manager.get_config("test_fixed_user", "support-agent", None)
        
        print(f"✅ Config retrieved: {config.model}")
        print(f"✅ Tracker attached: {config.tracker is not None}")
        
        if config.tracker:
            print(f"✅ Tracker type: {type(config.tracker)}")
            
            # Test tracking using the working pattern
            def dummy_function():
                import time
                time.sleep(0.1)
                return "test result"
            
            result = config_manager.track_metrics(config.tracker, dummy_function)
            print(f"✅ Tracking result: {result}")
            
            # Test direct tracker calls
            config.tracker.track_success()
            print("✅ Direct track_success() called")
            
            # Get summary
            try:
                summary = config.tracker.get_summary()
                print(f"✅ Tracker summary: {summary}")
            except Exception as e:
                print(f"⚠️ Summary error: {e}")
            
            # Flush
            config_manager.flush_metrics()
            
        else:
            print("❌ No tracker attached!")
        
        # Clean up
        config_manager.close()
        
        print("✅ Fixed ConfigManager test completed!")
        print("📊 Check LaunchDarkly dashboard for events from 'test_fixed_user'")
        
    except Exception as e:
        print(f"❌ Fixed ConfigManager test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_config_manager())
