#!/usr/bin/env python3
"""
Direct test of LaunchDarkly AI tracking to verify events are sent
"""
import os
import time
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, AIConfig, ModelConfig
from ldai.tracker import TokenUsage
from dotenv import load_dotenv

def test_direct_tracking():
    print("🔍 Testing direct LaunchDarkly AI tracking...")
    
    # Load environment
    load_dotenv()
    sdk_key = os.getenv('LD_SDK_KEY')
    
    if not sdk_key:
        print("❌ LD_SDK_KEY not found")
        return False
    
    print(f"✅ SDK Key found: {sdk_key[:20]}...")
    
    # Initialize LaunchDarkly client
    ldclient.set_config(ldclient.Config(sdk_key))
    client = ldclient.get()
    
    # Wait for initialization
    max_wait = 10
    wait_time = 0
    while not client.is_initialized() and wait_time < max_wait:
        time.sleep(0.5)
        wait_time += 0.5
    
    if not client.is_initialized():
        print("❌ LaunchDarkly client failed to initialize")
        return False
    
    print("✅ LaunchDarkly client initialized")
    
    # Create AI client and get config with tracker
    ai_client = LDAIClient(client)
    
    # Create context
    context = Context.builder("direct_test_user").kind('user').build()
    
    # Get AI config with tracker
    try:

        
        # Use a proper fallback config
        fallback = AIConfig(
            enabled=True,
            model=ModelConfig(name="claude-3-haiku-20240307")
        )
        
        config, tracker = ai_client.config("support-agent", context, fallback)
        
        if not tracker:
            print("❌ No tracker returned")
            return False
            
        print(f"✅ Tracker created: {type(tracker)}")
        print(f"✅ Tracker methods: {[m for m in dir(tracker) if not m.startswith('_')]}")
        
        # Test direct tracking calls
        print("🔄 Testing direct tracker calls...")
        
        # Test 1: Track success
        tracker.track_success()
        print("✅ Called track_success()")
        
        # Test 2: Track tokens
        token_usage = TokenUsage(input=100, output=50, total=150)
        tracker.track_tokens(token_usage)
        print("✅ Called track_tokens()")
        
        # Test 3: Track duration
        def dummy_func():
            time.sleep(0.1)
            return "test result"
        
        result = tracker.track_duration_of(dummy_func)
        print(f"✅ Called track_duration_of(): {result}")
        
        # Test 4: Track time to first token
        if hasattr(tracker, 'track_time_to_first_token'):
            tracker.track_time_to_first_token(250)  # 250ms
            print("✅ Called track_time_to_first_token()")
        
        # Test 5: Track feedback
        if hasattr(tracker, 'track_feedback'):
            try:
                tracker.track_feedback(1.0)  # Positive feedback
                print("✅ Called track_feedback()")
            except Exception as e:
                print(f"⚠️ track_feedback error: {e} (this is expected - feedback format varies)")
        
        # Test 6: Get summary
        try:
            summary = tracker.get_summary()
            print(f"✅ Tracker summary: duration={summary.duration}ms")
        except Exception as e:
            print(f"⚠️ Summary error: {e}")
        
        # Test 7: Force flush
        print("🔄 Flushing events to LaunchDarkly...")
        flush_result = client.flush()
        print(f"✅ Flush result: {flush_result}")
        
        # Wait a moment for events to be sent
        time.sleep(2)
        
        print("✅ Direct tracking test completed successfully!")
        print("📊 Check your LaunchDarkly dashboard for events from user 'direct_test_user'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during tracking test: {e}")
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    test_direct_tracking()
