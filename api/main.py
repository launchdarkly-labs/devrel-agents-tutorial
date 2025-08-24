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
    return await agent_service.process_message(
        user_id=request.user_id,
        message=request.message
    )