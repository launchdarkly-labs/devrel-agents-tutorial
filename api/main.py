from fastapi import FastAPI
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse
from .services.agent_service import AgentService
from .utils.console_capture import capture_console_output
from utils.logger import log_student, log_debug

load_dotenv()

app = FastAPI()

agent_service = AgentService()

@app.get("/health")
async def health():
    """Health check endpoint for monitoring"""
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Capture all console output during request processing
    with capture_console_output() as console_logs:
        message_text = request.message or ""
        log_student(f"API: Processing request from {request.user_id}")
        log_debug(f"API: Message: '{message_text[:50]}{'...' if len(message_text) > 50 else ''}', Context: {request.user_context}")

        # Server-side guard against empty/whitespace messages
        if not message_text.strip():
            return ChatResponse(
                id="validation",
                response="Please enter a question or pick an example query.",
                tool_calls=[],
                variation_key="validation",
                model="validation",
                agent_configurations=[],
                console_logs=console_logs
            )

        # SECURITY BOUNDARY: Pass sanitized conversation history only
        # Raw messages with PII are never sent to support agent - strict isolation maintained
        result = await agent_service.process_message(
            user_id=request.user_id,
            message=request.message,  # Raw message (security agent processes this)
            user_context=request.user_context,
            sanitized_conversation_history=request.sanitized_conversation_history  # PII-free history only
        )
        log_debug(f"API: Response ready ({len(result.response)} chars)")

        # Add captured console logs to the response
        result.console_logs = console_logs
        return result


@app.post("/admin/flush")
async def flush_metrics():
    """Force LaunchDarkly metrics to flush immediately - for simulation"""
    log_student("ADMIN: Flushing LaunchDarkly metrics...")
    agent_service.config_manager.flush_metrics()
    return {"success": True, "message": "Metrics flushed to LaunchDarkly"}

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """Submit user feedback for AI responses"""
    log_student(f"FEEDBACK: {feedback.feedback} from {feedback.source}")
    config_manager = agent_service.config_manager

    try:
        # Feedback is attributed to the support-agent variation this user is served
        support_config = await config_manager.get_config(
            feedback.user_id,
            "support-agent",
            feedback.user_context
        )

        # Same context the config was evaluated with, so feedback is attributed to the served variation
        ld_context = config_manager.build_context(feedback.user_id, feedback.user_context)
        success = config_manager.track_feedback(
            support_config,
            ld_context,
            thumbs_up=feedback.feedback == "positive"
        )
    except Exception as e:
        log_student(f"FEEDBACK ERROR: {e}")
        return FeedbackResponse(success=False, message=f"Failed to submit feedback: {e}")

    if not success:
        log_debug("FEEDBACK: Failed to submit feedback to LaunchDarkly")
        return FeedbackResponse(success=False, message="Failed to submit feedback to metrics tracking")

    log_debug(f"FEEDBACK SUBMITTED: {feedback.feedback} for {feedback.variation_key}")
    return FeedbackResponse(success=True, message="Feedback submitted successfully")
