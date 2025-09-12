from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List
import os
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse
from .services.agent_service import AgentService
from .utils.console_capture import capture_console_output
from utils.logger import log_student, log_debug

load_dotenv()

app = FastAPI()

agent_service = AgentService()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Capture all console output during request processing
    with capture_console_output() as console_logs:
        log_student(f"🌐 API: Received request from {request.user_id}")
        log_debug(f"🌐 API: Received chat request from user {request.user_id}: {request.message[:50]}...")
        try:
            result = await agent_service.process_message(
                user_id=request.user_id,
                message=request.message,
                user_context=request.user_context
            )
            log_debug(f"🌐 API: Returning response: {len(result.response) if result.response else 0} chars")
            
            # Add captured console logs to the response
            result.console_logs = console_logs
            return result
        except Exception as e:
            print(f"🌐 API ERROR: {e}")
            # Even on error, return the logs we captured
            raise


@app.post("/admin/flush")
async def flush_metrics():
    """Force LaunchDarkly metrics to flush immediately - for simulation"""
    print("🚀 ADMIN: Flushing LaunchDarkly metrics...")
    
    try:
        # Flush the LaunchDarkly client to send metrics immediately
        agent_service.flush_metrics()
        return {"success": True, "message": "Metrics flushed to LaunchDarkly"}
    except Exception as e:
        print(f"🚀 ADMIN FLUSH ERROR: {e}")
        return {"success": False, "message": f"Failed to flush metrics: {e}"}

# Cache clearing removed - simplified for demo

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """Submit user feedback for AI responses"""
    try:
        print(f"📝 FEEDBACK RECEIVED: {feedback.source} - {feedback.feedback} for message {feedback.message_id}")
        
        # Initialize AI metrics tracker with real LaunchDarkly tracker
        tracker = None
        try:
            from ai_metrics.metrics_tracker import AIMetricsTracker
            # Get a real LaunchDarkly AI config to get the tracker
            support_config = await agent_service.config_manager.get_config(feedback.user_id, "support-agent")
            tracker = AIMetricsTracker(support_config.tracker)
            print("✅ AI METRICS: Feedback tracker initialized with LaunchDarkly tracker")
        except Exception as e:
            print(f"⚠️  AI METRICS: Could not initialize tracker with LaunchDarkly: {e}")
            try:
                # Fallback to no tracker
                from ai_metrics.metrics_tracker import AIMetricsTracker
                tracker = AIMetricsTracker()
                print("⚠️  AI METRICS: Feedback tracker initialized without LaunchDarkly")
            except Exception as fallback_error:
                print(f"⚠️  AI METRICS: Could not initialize tracker at all: {fallback_error}")
        
        # Submit feedback to LaunchDarkly AI metrics
        if tracker:
            try:
                # Convert feedback format
                thumbs_up = feedback.feedback == "positive"
                
                await tracker.submit_feedback_async(
                    user_id=feedback.user_id,
                    request_id=feedback.message_id,
                    user_query=feedback.user_query,
                    ai_response=feedback.ai_response,
                    variation_key=feedback.variation_key,
                    model=feedback.model,
                    tool_calls=feedback.tool_calls,
                    thumbs_up=thumbs_up,
                    source=feedback.source
                )
                
                print(f"✅ FEEDBACK SUBMITTED: {feedback.source} {feedback.feedback} for {feedback.variation_key}")
                return FeedbackResponse(
                    success=True,
                    message=f"Feedback submitted successfully"
                )
                
            except Exception as e:
                print(f"❌ FEEDBACK ERROR: Failed to submit to LaunchDarkly: {e}")
                return FeedbackResponse(
                    success=False,
                    message=f"Failed to submit feedback: {e}"
                )
        else:
            # No tracker available - just log feedback
            print(f"📝 FEEDBACK LOGGED: {feedback.source} - {feedback.feedback} (no metrics tracking)")
            return FeedbackResponse(
                success=True,
                message="Feedback logged (metrics tracking unavailable)"
            )
        
    except Exception as e:
        print(f"❌ FEEDBACK ENDPOINT ERROR: {e}")
        return FeedbackResponse(
            success=False,
            message=f"Internal error: {e}"
        )