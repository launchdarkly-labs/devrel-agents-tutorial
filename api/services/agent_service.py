import uuid
from typing import List
from ..models import ChatResponse
from agents.support_agent import create_support_agent
from policy.config_manager import ConfigManager

class AgentService:
    def __init__(self):
        self.config_manager = ConfigManager()
        
    async def process_message(self, user_id: str, message: str) -> ChatResponse:
        # Get LaunchDarkly configuration
        config = await self.config_manager.get_config(user_id)
        
        # Create agent with configuration
        agent = create_support_agent(config)
        
        # Process message
        result = await agent.ainvoke({"user_input": message})
        
        return ChatResponse(
            id=str(uuid.uuid4()),
            response=result["response"],
            tool_calls=result.get("tool_calls", []),
            variation_key=config.variation_key
        )