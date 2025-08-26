import uuid
from typing import List
from langchain_core.messages import HumanMessage
from ..models import ChatResponse
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from agents.security_agent import create_security_agent
from policy.config_manager import ConfigManager

class AgentService:
    def __init__(self):
        self.config_manager = ConfigManager()
        
    async def process_message(self, user_id: str, message: str) -> ChatResponse:
        # Get LaunchDarkly configurations for all agents
        supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent")
        support_config = await self.config_manager.get_config(user_id, "support-agent") 
        security_config = await self.config_manager.get_config(user_id, "security-agent")
        
        # Create supervisor agent with all child agents
        supervisor_agent = create_supervisor_agent(supervisor_config, support_config, security_config)
        
        # Process message with supervisor state format
        initial_state = {
            "user_input": message,
            "current_agent": "",
            "security_cleared": False,
            "support_response": "",
            "final_response": "",
            "workflow_stage": "initial_security",
            "messages": [HumanMessage(content=message)]
        }
        
        result = await supervisor_agent.ainvoke(initial_state)
        
        return ChatResponse(
            id=str(uuid.uuid4()),
            response=result["final_response"],
            tool_calls=[],  # Supervisor manages tool calls internally
            variation_key=supervisor_config.variation_key,
            model=supervisor_config.model
        )