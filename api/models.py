from pydantic import BaseModel
from typing import Dict, List, Optional

class ChatRequest(BaseModel):
    user_id: str
    message: str

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