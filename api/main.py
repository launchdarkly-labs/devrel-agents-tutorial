from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List
import os
from dotenv import load_dotenv

from .models import ChatRequest, ChatResponse
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
            message=request.message
        )
        print(f"🌐 API: Returning response: {len(result.response) if result.response else 0} chars")
        return result
    except Exception as e:
        print(f"🌐 API ERROR: {e}")
        raise

# Cache clearing removed - simplified for demo