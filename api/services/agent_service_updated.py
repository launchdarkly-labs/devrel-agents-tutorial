import uuid
import time
from typing import List
from langchain_core.messages import HumanMessage
from ..models import ChatResponse, AgentConfig as APIAgentConfig
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from agents.security_agent import create_security_agent

# Use the updated ConfigManager
from policy.config_manager_updated import ConfigManager

class AgentService:
    def __init__(self):
        self.config_manager = ConfigManager()
        
        # Get advanced metrics tracker
        self.advanced_metrics = self.config_manager.get_advanced_metrics()
        
        # Log initialization status
        if self.config_manager.ld_client and self.config_manager.ld_client.is_initialized():
            print("✅ LaunchDarkly integration active")
        else:
            print("⚠️ LaunchDarkly integration inactive - using fallback configurations")
    
    def flush_metrics(self):
        """Flush LaunchDarkly metrics immediately"""
        try:
            # Use the config manager's flush method
            self.config_manager.flush_metrics()
            print("✅ METRICS: Successfully flushed to LaunchDarkly")
        except Exception as e:
            print(f"❌ METRICS FLUSH ERROR: {e}")
            raise
    
    def get_tool_performance_summary(self):
        """Get comprehensive tool performance analytics"""
        try:
            from ai_metrics.tool_performance import get_tool_tracker
            tool_tracker = get_tool_tracker()
            return tool_tracker.get_performance_summary()
        except Exception as e:
            print(f"⚠️ Tool performance summary unavailable: {e}")
            return {"error": str(e)}
    
    async def process_message(self, user_id: str, message: str, user_context: dict = None) -> ChatResponse:
        """Process message using refactored LDAI SDK pattern with advanced metrics tracking"""
        # Initialize request tracking
        session_id = user_context.get('session_id', str(uuid.uuid4())) if user_context else str(uuid.uuid4())
        request_id = None
        start_time = time.time()
        
        # Start advanced metrics tracking if available
        if self.advanced_metrics:
            try:
                request_id = self.advanced_metrics.start_request(
                    session_id=session_id,
                    agent_name="workflow",
                    variation="main",
                    model="supervisor",
                    user_context=user_context or {}
                )
                print(f"📊 Advanced metrics tracking started: {request_id}")
            except Exception as e:
                print(f"⚠️ Advanced metrics tracking start failed: {e}")
        
        try:
            # Batch fetch all agents in one call
            agents = await self.config_manager.get_agents_with_trackers(
                user_id,
                ["supervisor-agent", "support-agent", "security-agent"],
                user_context,
            )
            supervisor_config = agents["supervisor-agent"]
            support_config = agents["support-agent"]
            security_config = agents["security-agent"]
        
            print(f"🔍 AGENT CONFIGS LOADED:")
            print(f"   🎯 Supervisor: {supervisor_config.model}")
            print(f"   🔧 Support: {support_config.model}")
            print(f"   🔐 Security: {security_config.model}")
            
            # Create supervisor agent with all child agents
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
            
            print(f"🚀 STARTING WORKFLOW: {message[:100]}...")
            result = await supervisor_agent.ainvoke(initial_state)
            
            # Get actual tool calls used during the workflow
            actual_tool_calls = result.get("actual_tool_calls", [])
            if not actual_tool_calls:
                # Fallback to support_tool_calls if actual_tool_calls is not present
                actual_tool_calls = result.get("support_tool_calls", [])
            
            # Get detailed tool information with search queries from support agent
            tool_details = result.get("support_tool_details", [])
            
            print(f"✅ WORKFLOW COMPLETED:")
            print(f"   📊 Tools used: {actual_tool_calls}")
            print(f"   📊 Tool details: {len(tool_details)} items")
            print(f"   💬 Response length: {len(result['final_response'])} chars")
            
            # Track tool usage in advanced metrics if available
            if self.advanced_metrics and request_id:
                try:
                    for tool in actual_tool_calls:
                        self.advanced_metrics.track_tool_usage(request_id, tool, success=True)
                except Exception as e:
                    print(f"⚠️ Tool usage tracking failed: {e}")
            
            # Create agent configuration metadata showing actual usage
            agent_configurations = [
                APIAgentConfig(
                    agent_name="supervisor-agent",
                    variation_key=supervisor_config.variation_key,
                    model=supervisor_config.model,
                    tools=[]  # Supervisor doesn't use tools directly
                ),
                APIAgentConfig(
                    agent_name="security-agent", 
                    variation_key=security_config.variation_key,
                    model=security_config.model,
                    tools=[]  # Security agent uses native capabilities, minimal tools
                ),
                APIAgentConfig(
                    agent_name="support-agent",
                    variation_key=support_config.variation_key,
                    model=support_config.model, 
                    tools=actual_tool_calls,  # Show actual tools used as strings
                    tool_details=tool_details  # Show detailed tool info with search queries
                )
            ]
            
            # Calculate quality score and complete advanced metrics tracking
            final_response = result["final_response"]
            quality_score = None
            
            if self.advanced_metrics and request_id:
                try:
                    # Calculate response quality
                    from ai_metrics.metrics_tracker import analyze_response_quality
                    quality_score = analyze_response_quality(final_response)
                    
                    # Complete request tracking
                    self.advanced_metrics.complete_request(
                        request_id=request_id,
                        success=True,
                        quality_score=quality_score
                    )
                    
                    response_time = time.time() - start_time
                    print(f"📊 Advanced metrics: Quality={quality_score:.2f}, Time={response_time:.2f}s")
                except Exception as e:
                    print(f"⚠️ Advanced metrics completion failed: {e}")
            
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=final_response,
                tool_calls=actual_tool_calls,  # Show actual tools used
                variation_key=supervisor_config.variation_key,
                model=supervisor_config.model,  # Primary model
                agent_configurations=agent_configurations
            )
            
        except Exception as e:
            print(f"❌ WORKFLOW ERROR: {e}")
            
            # Complete advanced metrics tracking with error if available
            if self.advanced_metrics and request_id:
                try:
                    self.advanced_metrics.complete_request(
                        request_id=request_id,
                        success=False,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                except Exception as metrics_error:
                    print(f"⚠️ Error metrics tracking failed: {metrics_error}")
            
            # Return error response
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=f"I apologize, but I encountered an error processing your request: {e}",
                tool_calls=[],
                variation_key="error",
                model="error",
                agent_configurations=[]
            )