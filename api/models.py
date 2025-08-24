from pydantic import BaseModel
from typing import Dict, List, Optional

class ChatRequest(BaseModel):
    user_id: str
    message: str

class ChatResponse(BaseModel):
    id: str
    response: str
    tool_calls: List[str]
    variation_key: str