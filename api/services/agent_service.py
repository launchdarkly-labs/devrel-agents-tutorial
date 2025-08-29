import uuid
from typing import List
from langchain_core.messages import HumanMessage
from ..models import ChatResponse, AgentConfig
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from agents.security_agent import create_security_agent
from policy.config_manager import ConfigManager
from ai_metrics import AIMetricsTracker

class AgentService:
    def __init__(self):
        self.config_manager = ConfigManager()
    
    def flush_metrics(self):
        """Flush LaunchDarkly metrics immediately"""
        try:
            # Flush the LaunchDarkly client
            self.config_manager.ld_client.flush()
            print("✅ METRICS: Successfully flushed to LaunchDarkly")
        except Exception as e:
            print(f"❌ METRICS FLUSH ERROR: {e}")
            raise
        
    async def process_message(self, user_id: str, message: str, user_context: dict = None) -> ChatResponse:
        # Initialize AI metrics tracking
        # Use the support agent's tracker as the primary tracker (most likely to have metrics enabled)
        support_config = await self.config_manager.get_config(user_id, "support-agent", user_context)
        metrics_tracker = AIMetricsTracker(support_config.tracker)
        metrics_tracker.start_workflow(user_id, message)
        
        try:
            # Get LaunchDarkly configurations for all agents
            supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent", user_context) 
            security_config = await self.config_manager.get_config(user_id, "security-agent", user_context)
        
            # Create supervisor agent with all child agents - pass metrics tracker
            supervisor_agent = create_supervisor_agent(
                supervisor_config, support_config, security_config, 
                metrics_tracker=metrics_tracker
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
            
            workflow_start = metrics_tracker.track_agent_start("supervisor-workflow", supervisor_config.model, supervisor_config.variation_key)
            result = await supervisor_agent.ainvoke(initial_state)
            
            # Get actual tool calls used during the workflow
            actual_tool_calls = result.get("actual_tool_calls", [])
            if not actual_tool_calls:
                # Fallback to support_tool_calls if actual_tool_calls is not present
                actual_tool_calls = result.get("support_tool_calls", [])
            
            # Track workflow completion
            metrics_tracker.track_agent_completion(
                "supervisor-workflow", 
                supervisor_config.model, 
                supervisor_config.variation_key, 
                workflow_start, 
                actual_tool_calls, 
                True  # Success
            )
            
            # Finalize metrics tracking
            final_metrics = metrics_tracker.finalize_workflow(result["final_response"])
            
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
            
        except Exception as e:
            print(f"❌ WORKFLOW ERROR: {e}")
            
            # Track workflow failure
            if 'workflow_start' in locals():
                metrics_tracker.track_agent_completion(
                    "supervisor-workflow", 
                    supervisor_config.variation_key if 'supervisor_config' in locals() else "unknown",
                    supervisor_config.model if 'supervisor_config' in locals() else "unknown",
                    workflow_start, 
                    [], 
                    False,  # Failed
                    str(e)
                )
            
            # Finalize metrics even on failure
            metrics_tracker.finalize_workflow(f"Error: {e}")
            
            # Return error response
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=f"I apologize, but I encountered an error processing your request: {e}",
                tool_calls=[],
                variation_key="error",
                model="error",
                agent_configurations=[]
            )