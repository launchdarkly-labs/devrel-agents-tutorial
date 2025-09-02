#!/usr/bin/env python3
"""
Debug script to test satisfaction metrics tracking
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_metrics.metrics_tracker import AIMetricsTracker, FeedbackKind
from ldai.tracker import LDAIConfigTracker

async def test_feedback_tracking():
    """Test feedback tracking directly"""
    print("🔍 Testing feedback tracking directly...")
    
    # Create a mock tracker to test the method
    tracker = AIMetricsTracker()
    
    # Test the feedback method directly
    try:
        # This should fail since we don't have a real LD tracker, but let's see what happens
        print("Testing submit_feedback_async with mock tracker...")
        result = await tracker.submit_feedback_async(
            user_id="debug_user",
            request_id="debug_request_1",
            user_query="What is machine learning?",
            ai_response="Machine learning is AI that learns from data.",
            variation_key="test-variation",
            model="test-model",
            tool_calls=["search_v2"],
            thumbs_up=True,
            source="debug_test"
        )
        print(f"Feedback submission result: {result}")
    except Exception as e:
        print(f"Error in feedback submission: {e}")
        import traceback
        traceback.print_exc()

def test_feedback_kind():
    """Test FeedbackKind enum usage"""
    print("\n🔍 Testing FeedbackKind enum...")
    try:
        from ldai.tracker import FeedbackKind
        print(f"FeedbackKind.Positive: {FeedbackKind.Positive}")
        print(f"FeedbackKind.Negative: {FeedbackKind.Negative}")
        print(f"FeedbackKind type: {type(FeedbackKind.Positive)}")
        
        # Test creating a feedback dict
        feedback_dict = {
            "user_satisfaction": FeedbackKind.Positive
        }
        print(f"Feedback dict: {feedback_dict}")
        
    except Exception as e:
        print(f"Error with FeedbackKind: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_feedback_kind()
    asyncio.run(test_feedback_tracking())