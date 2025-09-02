#!/usr/bin/env python3
"""
Test script to verify UI feedback is working correctly
"""

import requests
import time
import json

def test_ui_feedback():
    """Test UI feedback flow"""
    print("🧪 Testing UI feedback flow...")
    
    # Simulate what the UI does when sending feedback
    feedback_data = {
        "user_id": "ui_test_user",
        "message_id": f"ui_test_msg_{int(time.time())}",
        "user_query": "What is machine learning?",
        "ai_response": "Machine learning is a type of artificial intelligence that enables computers to learn and make decisions without being explicitly programmed.",
        "feedback": "positive",  # This is what the UI sends
        "variation_key": "research-enhanced",
        "model": "claude-3-5-sonnet-20241022",
        "tool_calls": ["search_v2"],
        "source": "ui_test"
    }
    
    print("📤 Sending positive feedback from UI simulation...")
    response = requests.post("http://localhost:8000/feedback", json=feedback_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Feedback sent successfully: {result}")
    else:
        print(f"❌ Failed to send feedback: {response.status_code} - {response.text}")
        return False
    
    # Send negative feedback as well
    feedback_data["feedback"] = "negative"
    feedback_data["message_id"] = f"ui_test_msg_neg_{int(time.time())}"
    
    print("📤 Sending negative feedback from UI simulation...")
    response = requests.post("http://localhost:8000/feedback", json=feedback_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Negative feedback sent successfully: {result}")
    else:
        print(f"❌ Failed to send negative feedback: {response.status_code} - {response.text}")
        return False
    
    # Flush metrics to LaunchDarkly
    print("🚀 Flushing metrics to LaunchDarkly...")
    flush_response = requests.post("http://localhost:8000/admin/flush")
    
    if flush_response.status_code == 200:
        result = flush_response.json()
        print(f"✅ Metrics flushed: {result}")
    else:
        print(f"❌ Failed to flush metrics: {flush_response.status_code} - {flush_response.text}")
        return False
        print("✅ UI feedback test completed!")
    print("📊 Check your LaunchDarkly dashboard for feedback events from user 'ui_test_user'")
    print("⏰ Note: It may take 1-2 minutes for feedback to appear in the dashboard")
    
    return True

if __name__ == "__main__":
    test_ui_feedback()