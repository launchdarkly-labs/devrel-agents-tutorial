from pydantic import BaseModel
from typing import Dict, List, Optional

class ChatRequest(BaseModel):
    user_id: str
    message: str  # Raw user input (goes to security agent only)
    user_context: Optional[Dict] = None  # Geographic and other targeting attributes
    # SECURITY BOUNDARY: Only sanitized conversation history is accepted
    # This ensures support agent never sees raw PII from previous messages
    sanitized_conversation_history: Optional[List[Dict]] = None  # Previously redacted messages only

class AgentConfig(BaseModel):
    agent_name: str
    variation_key: str
    model: str
    tools: List[str]  # Available tools configured from LaunchDarkly
    tools_used: Optional[List[str]] = None  # Actual tools that were executed
    tool_details: Optional[List[Dict]] = None  # Optional detailed tool info with search queries
    # PII detection fields for security agent
    detected: Optional[bool] = None
    types: Optional[List[str]] = None
    redacted: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    response: str
    tool_calls: List[str]
    variation_key: str
    model: str
    agent_configurations: Optional[List[AgentConfig]] = None
    console_logs: Optional[List[str]] = None

class FeedbackRequest(BaseModel):
    user_id: str
    message_id: str
    user_query: str
    ai_response: str
    feedback: str  # "positive" or "negative"
    variation_key: str
    model: str
    tool_calls: List[str]
    source: str  # "real_user" or "simulated"
    user_context: Optional[Dict] = None  # Geographic and plan attributes for LaunchDarkly targeting
    
class FeedbackResponse(BaseModel):
    success: bool
    message: str