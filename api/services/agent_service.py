import uuid
from typing import List
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
from ..models import ChatResponse, AgentConfig as APIAgentConfig
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from agents.security_agent import create_security_agent
from config_manager import FixedConfigManager as ConfigManager
from utils.logger import log_student, log_debug, log_info

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
        
    async def process_message(self, user_id: str, message: str, user_context: dict = None, sanitized_conversation_history: list = None) -> ChatResponse:
        """Process message using refactored LDAI SDK pattern"""
        try:
            log_debug(f"🎯 AGENT SERVICE: Processing message for {user_id}")
            
            # Get LaunchDarkly LDAI configurations for all agents
            log_debug("🎯 AGENT SERVICE: Loading agent configurations...")
            supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent", user_context) 
            support_config = await self.config_manager.get_config(user_id, "support-agent", user_context)
            security_config = await self.config_manager.get_config(user_id, "security-agent", user_context)
        
            log_student(f"🔍 LDAI: 3 agents configured")
            log_debug(f"🔍 LDAI: Supervisor({supervisor_config.model.name}), Support({support_config.model.name}), Security({security_config.model.name})")
            
            # Create supervisor agent with all child agents using LDAI SDK pattern
            supervisor_agent = create_supervisor_agent(
                supervisor_config, 
                support_config, 
                security_config,
                self.config_manager
            )
            
            # ===== SECURITY BOUNDARY: PII ISOLATION SETUP =====
            # Convert sanitized conversation history to LangChain messages
            # CRITICAL: Support agent will ONLY see these sanitized messages
            sanitized_langchain_messages = []
            if sanitized_conversation_history:
                for msg in sanitized_conversation_history:
                    if msg.get("role") == "user":
                        sanitized_langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        sanitized_langchain_messages.append(AIMessage(content=msg["content"]))
            
            # Add current raw message for security agent processing
            current_raw_message = HumanMessage(content=message)
            
            # Process message with supervisor state format
            initial_state = {
                "user_input": message,  # Raw message (security agent only)
                "current_agent": "",
                "security_cleared": False,
                "support_response": "",
                "final_response": "",
                "workflow_stage": "initial_security",
                "messages": [current_raw_message],  # Security agent gets raw message
                "sanitized_messages": sanitized_langchain_messages,  # SUPPORT AGENT ONLY gets these
                "processed_user_input": "",
                "pii_detected": False,
                "pii_types": [],
                "redacted_text": message,
                "support_tool_calls": [],
                "support_tool_details": []
            }
            
            log_student(f"🎯 WORKFLOW: Starting security check")
            log_debug(f"🔒 PII PROTECTION: Processing message through security agent first")
            result = await supervisor_agent.ainvoke(initial_state)
            
            # Get actual tool calls used during the workflow
            actual_tool_calls = result.get("actual_tool_calls", [])
            if not actual_tool_calls:
                # Fallback to support_tool_calls if actual_tool_calls is not present
                actual_tool_calls = result.get("support_tool_calls", [])
            
            # Get detailed tool information with search queries from support agent
            tool_details = result.get("support_tool_details", [])
            
            # Get security agent PII detection results and tool details
            security_detected = result.get("pii_detected", False)
            security_types = result.get("pii_types", [])
            security_redacted = result.get("redacted_text", message)
            security_tool_details = result.get("security_tool_details", [])
            
            # Create consolidated workflow summary for students
            tools_summary = f"{len(actual_tool_calls)} tools used" if actual_tool_calls else "No tools used"
            pii_status = f"PII detected: {security_detected}"
            response_length = len(result['final_response'])
            
            log_student(f"✅ WORKFLOW COMPLETE: {tools_summary}, {pii_status}, Response: {response_length} chars")
            
            log_debug(f"✅ WORKFLOW: Tools={len(actual_tool_calls)}, Details={len(tool_details)}, Response={len(result['final_response'])}chars, PII={security_detected}")
            
            # Create agent configuration metadata showing actual usage
            # Extract variation keys from AI config (may be available via to_dict)
            def get_variation_key(ai_config, agent_name):
                try:
                    # Use user context to determine correct variation rather than relying on model mapping
                    # This is more reliable since LaunchDarkly targeting may have propagation delays
                    user_ctx = user_context or {}
                    country = user_ctx.get('country', 'US')
                    plan = user_ctx.get('plan', 'free')
                    
                    # Determine geographic region
                    eu_countries = ["DE", "FR", "ES", "IT", "NL", "BE", "AT", "PL", "PT", "GR", "CZ", "HU", "SE", "DK", "FI"]
                    is_eu = country in eu_countries
                    
                    # Determine correct variation based on user context
                    if agent_name == "supervisor-agent":
                        return "supervisor-basic"  # Supervisor always uses basic variation
                    elif agent_name == "security-agent":
                        return "strict-security" if is_eu else "basic-security"
                    elif agent_name == "support-agent":
                        if is_eu:
                            return "eu-paid" if plan == "paid" else "eu-free"
                        else:
                            return "other-paid" if plan == "paid" else "other-free"
                    
                    log_debug(f"🎯 USER CONTEXT: {agent_name} → {country}/{plan}")
                    return 'default'
                except Exception as e:
                    log_debug(f"🎯 VARIATION ERROR: {e}")
                    return 'default'
            
            def get_tools_list(ai_config):
                try:
                    config_dict = ai_config.to_dict()
                    tools = config_dict.get('model', {}).get('parameters', {}).get('tools', [])
                    tool_names = [tool.get('name', 'unknown') for tool in tools]
                    log_debug(f"🎯 EXTRACTED TOOLS: {tool_names}")
                    return tool_names
                except Exception as e:
                    log_debug(f"🎯 TOOLS EXTRACTION ERROR: {e}")
                    return []
            
            # Extract tools list from configs
            security_tools = get_tools_list(security_config)
            support_tools = get_tools_list(support_config)
            
            # Determine which tools were actually used by each agent
            security_tools_used = []
            support_tools_used = actual_tool_calls  # Support agent is the primary tool user
            
            agent_configurations = [
                APIAgentConfig(
                    agent_name="supervisor-agent",
                    variation_key=get_variation_key(supervisor_config, "supervisor-agent"),
                    model=supervisor_config.model.name,
                    tools=[],  # Supervisor doesn't have tools available
                    tools_used=[]  # Supervisor doesn't use tools directly
                ),
                APIAgentConfig(
                    agent_name="security-agent", 
                    variation_key=get_variation_key(security_config, "security-agent"),
                    model=security_config.model.name,
                    tools=security_tools,  # Show configured tools
                    tools_used=security_tools_used,  # Show actual tools used
                    tool_details=security_tool_details,  # Show security tool details with PII results
                    # Pass PII detection results to UI
                    detected=security_detected,
                    types=security_types,
                    redacted=security_redacted
                ),
                APIAgentConfig(
                    agent_name="support-agent",
                    variation_key=get_variation_key(support_config, "support-agent"),
                    model=support_config.model.name, 
                    tools=support_tools,  # Show configured tools from LaunchDarkly
                    tools_used=support_tools_used,  # Show actual tools executed
                    tool_details=tool_details  # Show detailed tool info with search queries
                )
            ]
            
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=result["final_response"],
                tool_calls=actual_tool_calls,  # Show actual tools used
                variation_key=get_variation_key(supervisor_config, "supervisor-agent"),  # Use actual LaunchDarkly variation
                model=supervisor_config.model.name,  # Primary model
                agent_configurations=agent_configurations
            )
            
        except Exception as e:
            log_student(f"❌ LDAI WORKFLOW ERROR: {e}")
            
            # Return error response
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=f"I apologize, but I encountered an error processing your request: {e}",
                tool_calls=[],
                variation_key="error",
                model="error",
                agent_configurations=[]
            )