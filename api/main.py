from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List
import os
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse
from .services.agent_service import AgentService

load_dotenv()

app = FastAPI()

agent_service = AgentService()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print(f"🌐 API: Received chat request from user {request.user_id}: {request.message[:50]}...")
    try:
        result = await agent_service.process_message(
            user_id=request.user_id,
            message=request.message,
            user_context=request.user_context
        )
        print(f"🌐 API: Returning response: {len(result.response) if result.response else 0} chars")
        return result
    except Exception as e:
        print(f"🌐 API ERROR: {e}")
        raise

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback for a chat response - for traffic simulation"""
    print(f"📝 FEEDBACK: User {request.user_id} gave feedback for {request.request_id}")
    print(f"📝 FEEDBACK: Thumbs up: {request.thumbs_up}, Rating: {request.rating}")
    
    try:
        # In a real system, you'd store this feedback in a database
        # For the simulation, we just log it and could send to LaunchDarkly as a custom event
        
        # TODO: Send feedback to LaunchDarkly as custom events for experiment tracking
        # ldclient.track('feedback_received', user_context, {'thumbs_up': request.thumbs_up, 'rating': request.rating})
        
        return FeedbackResponse(
            success=True, 
            message=f"Feedback received for request {request.request_id}"
        )
    except Exception as e:
        print(f"📝 FEEDBACK ERROR: {e}")
        return FeedbackResponse(
            success=False,
            message=f"Failed to record feedback: {e}"
        )

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
        
        # Initialize AI metrics tracker if needed
        tracker = None
        try:
            from ai_metrics.metrics_tracker import AIMetricsTracker
            tracker = AIMetricsTracker()
            print("✅ AI METRICS: Feedback tracker initialized")
        except Exception as e:
            print(f"⚠️  AI METRICS: Could not initialize tracker: {e}")
        
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