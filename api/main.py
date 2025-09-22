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
        message_text = request.message or ""
        log_student(f"🌐 API: Processing request from {request.user_id}")
        log_debug(f"🌐 API: Message: '{message_text[:50]}{'...' if len(message_text) > 50 else ''}', Context: {request.user_context}")
        
        # Server-side guard against empty/whitespace messages
        if not message_text.strip():
            log_debug("🌐 API: Empty message - returning validation response")
            from .models import ChatResponse as CR
            validation_response = CR(
                id="validation",
                response="Please enter a question or pick an example query.",
                tool_calls=[],
                variation_key="validation",
                model="validation",
                agent_configurations=[],
                console_logs=console_logs
            )
            return validation_response
        try:
            # SECURITY BOUNDARY: Pass sanitized conversation history only
            # Raw messages with PII are never sent to support agent - strict isolation maintained
            result = await agent_service.process_message(
                user_id=request.user_id,
                message=request.message,  # Raw message (security agent processes this)
                user_context=request.user_context,
                sanitized_conversation_history=request.sanitized_conversation_history  # PII-free history only
            )
            log_debug(f"🌐 API: Response ready ({len(result.response) if result.response else 0} chars)")
            
            # Add captured console logs to the response
            result.console_logs = console_logs
            return result
        except Exception as e:
            import traceback
            log_student(f"🌐 API ERROR: {e}")
            log_debug(f"🌐 API ERROR TRACEBACK: {traceback.format_exc()}")
            # Even on error, return the logs we captured
            raise


@app.post("/admin/flush")
async def flush_metrics():
    """Force LaunchDarkly metrics to flush immediately - for simulation"""
    log_student("🚀 ADMIN: Flushing LaunchDarkly metrics...")
    
    try:
        # Flush the LaunchDarkly client to send metrics immediately
        agent_service.flush_metrics()
        return {"success": True, "message": "Metrics flushed to LaunchDarkly"}
    except Exception as e:
        log_student(f"🚀 ADMIN FLUSH ERROR: {e}")
        return {"success": False, "message": f"Failed to flush metrics: {e}"}

# Cache clearing removed - simplified for demo

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """Submit user feedback for AI responses"""
    try:
        log_student(f"📝 FEEDBACK: {feedback.feedback} from {feedback.source}")
        
        # Initialize AI metrics tracker with real LaunchDarkly tracker
        tracker = None
        try:
            from ai_metrics.metrics_tracker import AIMetricsTracker
            # Get a real LaunchDarkly AI config to get the tracker
            support_config = await agent_service.config_manager.get_config(feedback.user_id, "support-agent")
            tracker = AIMetricsTracker(support_config.tracker)
            log_debug("✅ AI METRICS: Feedback tracker initialized with LaunchDarkly")
        except Exception as e:
            log_debug(f"⚠️  AI METRICS: LaunchDarkly initialization failed: {e}")
            try:
                # Fallback to no tracker
                from ai_metrics.metrics_tracker import AIMetricsTracker
                tracker = AIMetricsTracker()
                log_debug("⚠️  AI METRICS: Using fallback tracker")
            except Exception as fallback_error:
                log_debug(f"⚠️  AI METRICS: Tracker initialization failed: {fallback_error}")
        
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
                
                log_debug(f"✅ FEEDBACK SUBMITTED: {feedback.feedback} for {feedback.variation_key}")
                return FeedbackResponse(
                    success=True,
                    message=f"Feedback submitted successfully"
                )
                
            except Exception as e:
                log_student(f"❌ FEEDBACK ERROR: {e}")
                return FeedbackResponse(
                    success=False,
                    message=f"Failed to submit feedback: {e}"
                )
        else:
            # No tracker available - just log feedback
            log_debug(f"📝 FEEDBACK LOGGED: {feedback.feedback} (no metrics tracking)")
            return FeedbackResponse(
                success=True,
                message="Feedback logged (metrics tracking unavailable)"
            )
        
    except Exception as e:
        log_student(f"❌ FEEDBACK ENDPOINT ERROR: {e}")
        return FeedbackResponse(
            success=False,
            message=f"Internal error: {e}"
        )