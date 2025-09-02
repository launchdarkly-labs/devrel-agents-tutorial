#!/usr/bin/env python3
"""
Comprehensive debug script to test satisfaction metrics tracking with real LD tracker
"""

import asyncio
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, AIConfig, ModelConfig
from ldai.tracker import TokenUsage, FeedbackKind

def test_direct_feedback():
    """Test feedback tracking with a real LaunchDarkly tracker"""
    print("🔍 Testing feedback tracking with real LD tracker...")
    
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
    context = Context.builder("feedback_test_user").kind('user').build()
    
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
        
        # Test success tracking
        tracker.track_success()
        print("✅ Called track_success()")
        
        # Test the CORRECT way to call track_feedback
        print("🔄 Testing track_feedback with proper dictionary format...")
        try:
            # This is the correct format according to the documentation
            feedback_dict = {
                "user_satisfaction": FeedbackKind.Positive
            }
            tracker.track_feedback(feedback_dict)
            print("✅ Called track_feedback() with proper dictionary format")
        except Exception as e:
            print(f"❌ track_feedback with dictionary failed: {e}")
            import traceback
            traceback.print_exc()
            
        # Test with different feedback types
        try:
            feedback_dict = {
                "user_satisfaction": FeedbackKind.Negative
            }
            tracker.track_feedback(feedback_dict)
            print("✅ Called track_feedback() with negative feedback")
        except Exception as e:
            print(f"❌ track_feedback with negative feedback failed: {e}")
            
        # Test with multiple feedback types
        try:
            feedback_dict = {
                "user_satisfaction": FeedbackKind.Positive,
                "content_quality": FeedbackKind.Positive
            }
            tracker.track_feedback(feedback_dict)
            print("✅ Called track_feedback() with multiple feedback types")
        except Exception as e:
            print(f"❌ track_feedback with multiple feedback types failed: {e}")
        
        # Get summary
        try:
            summary = tracker.get_summary()
            print(f"✅ Tracker summary: duration={summary.duration}ms")
        except Exception as e:
            print(f"⚠️ Summary error: {e}")
        
        # Force flush
        print("🔄 Flushing events to LaunchDarkly...")
        flush_result = client.flush()
        print(f"✅ Flush result: {flush_result}")
        
        # Wait a moment for events to be sent
        time.sleep(2)
        
        print("✅ Direct feedback tracking test completed successfully!")
        print("📊 Check your LaunchDarkly dashboard for events from user 'feedback_test_user'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during feedback tracking test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = test_direct_feedback()
    exit(0 if success else 1)