import uuid
from typing import List
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from ..models import ChatResponse, AgentConfig as APIAgentConfig
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from agents.security_agent import create_security_agent
from fixed_config_manager import FixedConfigManager as ConfigManager

# Ensure .env is loaded before ConfigManager initialization
load_dotenv()

class AgentService:
    def __init__(self):
        self.config_manager = ConfigManager()
        # Clear LaunchDarkly cache on startup to get latest configs
        self.config_manager.clear_cache()
    
    def flush_metrics(self):
        """Flush LaunchDarkly metrics immediately"""
        try:
            # Use the config manager's close method which handles flushing
            self.config_manager.close()
            print("✅ METRICS: Successfully flushed to LaunchDarkly")
        except Exception as e:
            print(f"❌ METRICS FLUSH ERROR: {e}")
            raise
        
    async def process_message(self, user_id: str, message: str, user_context: dict = None) -> ChatResponse:
        """Process message using refactored LDAI SDK pattern"""
        try:
            # Get LaunchDarkly LDAI configurations for all agents
            supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent", user_context) 
            support_config = await self.config_manager.get_config(user_id, "support-agent", user_context)
            security_config = await self.config_manager.get_config(user_id, "security-agent", user_context)
        
            print(f"🔍 LDAI CONFIGS LOADED:")
            print(f"   🎯 Supervisor: {supervisor_config.model} (enabled: True)")
            print(f"   🔧 Support: {support_config.model} (enabled: True)")
            print(f"   🔐 Security: {security_config.model} (enabled: True)")
            
            # Create supervisor agent with all child agents using LDAI SDK pattern
            supervisor_agent = create_supervisor_agent(
                supervisor_config, 
                support_config, 
                security_config,
                self.config_manager
            )
            
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
            
            print(f"🚀 STARTING LDAI WORKFLOW: {message[:100]}...")
            result = await supervisor_agent.ainvoke(initial_state)
            
            # Get actual tool calls used during the workflow
            actual_tool_calls = result.get("actual_tool_calls", [])
            if not actual_tool_calls:
                # Fallback to support_tool_calls if actual_tool_calls is not present
                actual_tool_calls = result.get("support_tool_calls", [])
            
            # Get detailed tool information with search queries from support agent
            tool_details = result.get("support_tool_details", [])
            
            print(f"✅ LDAI WORKFLOW COMPLETED:")
            print(f"   📊 Tools used: {actual_tool_calls}")
            print(f"   📊 Tool details: {len(tool_details)} items")
            print(f"   💬 Response length: {len(result['final_response'])} chars")
            
            # Create agent configuration metadata showing actual usage
            agent_configurations = [
                APIAgentConfig(
                    agent_name="supervisor-agent",
                    variation_key=supervisor_config.variation_key,  # Use actual LaunchDarkly variation
                    model=supervisor_config.model,
                    tools=[]  # Supervisor doesn't use tools directly
                ),
                APIAgentConfig(
                    agent_name="security-agent", 
                    variation_key=security_config.variation_key,  # Use actual LaunchDarkly variation
                    model=security_config.model,
                    tools=[]  # Security agent uses native capabilities, minimal tools
                ),
                APIAgentConfig(
                    agent_name="support-agent",
                    variation_key=support_config.variation_key,  # Use actual LaunchDarkly variation
                    model=support_config.model, 
                    tools=actual_tool_calls,  # Show actual tools used as strings
                    tool_details=tool_details  # Show detailed tool info with search queries
                )
            ]
            
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=result["final_response"],
                tool_calls=actual_tool_calls,  # Show actual tools used
                variation_key=supervisor_config.variation_key,  # Use actual LaunchDarkly variation
                model=supervisor_config.model,  # Primary model
                agent_configurations=agent_configurations
            )
            
        except Exception as e:
            print(f"❌ LDAI WORKFLOW ERROR: {e}")
            
            # Return error response
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=f"I apologize, but I encountered an error processing your request: {e}",
                tool_calls=[],
                variation_key="error",
                model="error",
                agent_configurations=[]
            )