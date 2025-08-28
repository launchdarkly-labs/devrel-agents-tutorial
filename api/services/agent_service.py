import uuid
from typing import List
from langchain_core.messages import HumanMessage
from ..models import ChatResponse, AgentConfig
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
        
        # Get actual tool calls used during the workflow
        actual_tool_calls = result.get("actual_tool_calls", [])
        if not actual_tool_calls:
            # Fallback to support_tool_calls if actual_tool_calls is not present
            actual_tool_calls = result.get("support_tool_calls", [])
        
        # Create agent configuration metadata showing actual usage
        agent_configurations = [
            AgentConfig(
                agent_name="supervisor-agent",
                variation_key=supervisor_config.variation_key,
                model=supervisor_config.model,
                tools=[]  # Supervisor doesn't use tools directly
            ),
            AgentConfig(
                agent_name="security-agent", 
                variation_key=security_config.variation_key,
                model=security_config.model,
                tools=[]  # Security agent uses native capabilities, no tools
            ),
            AgentConfig(
                agent_name="support-agent",
                variation_key=support_config.variation_key,
                model=support_config.model, 
                tools=actual_tool_calls  # Show actual tools used
            )
        ]
        
        return ChatResponse(
            id=str(uuid.uuid4()),
            response=result["final_response"],
            tool_calls=actual_tool_calls,  # Show actual tools used
            variation_key=supervisor_config.variation_key,  # Primary variation
            model=supervisor_config.model,  # Primary model
            agent_configurations=agent_configurations
        )