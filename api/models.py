from pydantic import BaseModel
from typing import Dict, List, Optional

class ChatRequest(BaseModel):
    user_id: str
    message: str
    user_context: Optional[Dict] = None  # Geographic and other targeting attributes

class AgentConfig(BaseModel):
    agent_name: str
    variation_key: str
    model: str
    tools: List[str]

class ChatResponse(BaseModel):
    id: str
    response: str
    tool_calls: List[str]
    variation_key: str
    model: str
    agent_configurations: Optional[List[AgentConfig]] = None

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
    
class FeedbackResponse(BaseModel):
    success: bool
    message: str