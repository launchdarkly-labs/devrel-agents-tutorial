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
    """
    Multi-Agent Orchestration Service

    LANGGRAPH INTEGRATION PATTERN:
    This service creates and executes the supervisor agent workflow,
    which internally manages multiple specialized agents using LangGraph.

    WORKFLOW ARCHITECTURE:
    1. AgentService receives HTTP requests
    2. Creates supervisor agent (LangGraph workflow)
    3. Supervisor orchestrates security and support agents
    4. Returns unified response with all agent results

    PII SECURITY ISOLATION:
    - Raw user input goes to security agent first
    - Support agent only receives sanitized data
    - Security boundaries are enforced at the state level
    """
    def __init__(self):
        # Initialize LaunchDarkly configuration manager
        self.config_manager = ConfigManager()
        # Clear LaunchDarkly cache on startup to get latest configs
        self.config_manager.clear_cache()
    
    def flush_metrics(self):
        """Flush LaunchDarkly metrics immediately"""
        try:
            # Use the config manager's close method which handles flushing
            self.config_manager.close()
            print(" METRICS: Successfully flushed to LaunchDarkly")
        except Exception as e:
            print(f" METRICS FLUSH ERROR: {e}")
            raise
        
    async def process_message(self, user_id: str, message: str, user_context: dict = None, sanitized_conversation_history: list = None) -> ChatResponse:
        """
        Process Message through Multi-Agent LangGraph Workflow

        WORKFLOW OVERVIEW:
        1. Fetch LaunchDarkly AI Configs for all 3 agents
        2. Create supervisor agent (LangGraph workflow)
        3. Execute workflow with PII security isolation
        4. Return structured response with agent details

        STATE FLOW:
        - Initial state contains raw user input
        - Security agent processes and sanitizes data
        - Support agent operates on sanitized data only
        - Final state contains responses from both agents

        LANGGRAPH INTEGRATION:
        - Uses supervisor.ainvoke() to execute workflow
        - State flows through multiple agents automatically
        - PII isolation enforced through state field management
        """
        try:
            log_debug(f"AGENT SERVICE: Processing message for {user_id}")

            # =============================================
            # INPUT VALIDATION & SAFETY CHECKS
            # =============================================

            # Validate message content
            if not message or not message.strip():
                return ChatResponse(
                    id=str(uuid.uuid4()),
                    response="Please provide a message to process.",
                    tool_calls=[],
                    variation_key="validation_error",
                    model="validation",
                    agent_configurations=[]
                )

            # Validate message length (prevent extremely long inputs)
            max_message_length = 5000  # Reasonable limit for tutorial use
            if len(message) > max_message_length:
                return ChatResponse(
                    id=str(uuid.uuid4()),
                    response=f"Message too long ({len(message)} characters). Please limit to {max_message_length} characters.",
                    tool_calls=[],
                    variation_key="validation_error",
                    model="validation",
                    agent_configurations=[]
                )

            # Validate user_id
            if not user_id or not user_id.strip():
                user_id = "anonymous_user"  # Provide safe default
                log_debug("VALIDATION: Empty user_id provided, using 'anonymous_user'")

            # Validate user_context structure
            if user_context is not None and not isinstance(user_context, dict):
                log_debug("VALIDATION: Invalid user_context type, using empty dict")
                user_context = {}  # Safe fallback

            # Validate sanitized_conversation_history
            if sanitized_conversation_history is not None and not isinstance(sanitized_conversation_history, list):
                log_debug("VALIDATION: Invalid conversation history type, ignoring")
                sanitized_conversation_history = None  # Safe fallback

            log_debug("✅ INPUT VALIDATION: All inputs validated successfully")

            # Get LaunchDarkly LDAI configurations for all agents
            log_debug(" AGENT SERVICE: Loading agent configurations...")
            supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent", user_context) 
            support_config = await self.config_manager.get_config(user_id, "support-agent", user_context)
            security_config = await self.config_manager.get_config(user_id, "security-agent", user_context)
        
            log_student(f"LDAI: 3 agents configured")
            log_debug(f"LDAI: Supervisor({supervisor_config.model.name}), Support({support_config.model.name}), Security({security_config.model.name})")
            
            # Create supervisor agent with all child agents using LDAI SDK pattern
            supervisor_agent = create_supervisor_agent(
                supervisor_config, 
                support_config, 
                security_config,
                self.config_manager
            )
            
            # =============================================
            # PII SECURITY BOUNDARY SETUP
            # =============================================

            # Convert sanitized conversation history to LangChain messages
            # CRITICAL: Support agent will ONLY see these sanitized messages
            sanitized_langchain_messages = []
            if sanitized_conversation_history:
                for msg in sanitized_conversation_history:
                    # Validate message structure
                    if not isinstance(msg, dict):
                        log_debug("VALIDATION: Skipping invalid message in conversation history")
                        continue

                    role = msg.get("role")
                    content = msg.get("content")

                    # Validate content exists and is not empty
                    if not content or not content.strip():
                        log_debug(f"VALIDATION: Skipping empty message with role {role}")
                        continue

                    # Convert to LangChain messages
                    if role == "user":
                        sanitized_langchain_messages.append(HumanMessage(content=content.strip()))
                    elif role == "assistant":
                        sanitized_langchain_messages.append(AIMessage(content=content.strip()))
                    else:
                        log_debug(f"VALIDATION: Skipping message with unknown role: {role}")

                # === MESSAGE MEMORY MANAGEMENT ===
                # Trim conversation history to prevent context overflow
                # This is especially important for long-running conversations
                from agents.supervisor_agent import trim_message_history
                sanitized_langchain_messages = trim_message_history(sanitized_langchain_messages, max_messages=8)

            # Add current raw message for security agent processing
            current_raw_message = HumanMessage(content=message)
            
            # =============================================
            # LANGGRAPH INITIAL STATE CONSTRUCTION
            # =============================================

            # Create initial state for LangGraph workflow
            # This state object will flow through all agents
            initial_state = {
                # === CORE MESSAGE FLOW ===
                "user_input": message.strip(),                  # Raw message (security agent only) - trimmed
                "messages": [current_raw_message],              # Security agent gets raw message
                "final_response": "",

                # === LAUNCHDARKLY TARGETING ===
                "user_id": user_id,                             # Validated user ID
                "user_context": user_context or {},             # Validated user context

                # === WORKFLOW ORCHESTRATION ===
                "current_agent": "",                            # Supervisor will determine first agent
                "workflow_stage": "pii_prescreen",              # Start with intelligent PII pre-screening
                "security_cleared": False,

                # === SUPPORT AGENT RESULTS ===
                "support_response": "",
                "support_tool_calls": [],
                "support_tool_details": [],

                # === PII SECURITY BOUNDARY ===
                "sanitized_messages": sanitized_langchain_messages,  # SUPPORT AGENT ONLY gets these (validated)
                "processed_user_input": "",                     # Will be set by security agent
                "pii_detected": False,                          # Will be set by security agent
                "pii_types": [],                                # Will be set by security agent
                "redacted_text": message.strip(),               # Will be updated by security agent
            }
            
            # =============================================
            # LANGGRAPH WORKFLOW EXECUTION
            # =============================================

            log_student(f"INTELLIGENT ROUTING: Starting PII pre-screening analysis")
            log_debug(f"🔒 PII PROTECTION: Enhanced supervisor will decide routing path")

            # Execute the LangGraph workflow
            # The supervisor will orchestrate security and support agents automatically
            result = await supervisor_agent.ainvoke(initial_state)
            
            actual_tool_calls = result.get("support_tool_calls", [])
            tool_details = result.get("support_tool_details", [])
            
            # Get security agent PII detection results and tool details
            security_detected = result.get("pii_detected", False)
            security_types = result.get("pii_types", [])
            security_redacted = result.get("redacted_text", message)
            security_tool_details = result.get("security_tool_details", [])
            
            log_student(f"WORKFLOW COMPLETE: PII detected: {security_detected}")
            
            # Create agent configuration metadata showing actual usage
            # Extract actual variation key from LaunchDarkly AI config
            def get_variation_key(ai_config, agent_name):
                try:
                    # The variation key is stored in the tracker object
                    if hasattr(ai_config, 'tracker') and hasattr(ai_config.tracker, '_variation_key'):
                        variation_key = ai_config.tracker._variation_key
                        log_debug(f"VARIATION EXTRACTED for {agent_name}: {variation_key}")
                        return variation_key
                    else:
                        log_debug(f"VARIATION NOT FOUND for {agent_name}: no tracker._variation_key")
                        return 'default'
                except Exception as e:
                    log_debug(f"VARIATION EXTRACTION ERROR for {agent_name}: {e}")
                    return 'default'
            
            def get_tools_list(ai_config):
                try:
                    config_dict = ai_config.to_dict()
                    tools = config_dict.get('model', {}).get('parameters', {}).get('tools', [])
                    tool_names = [tool.get('name', 'unknown') for tool in tools]
                    log_debug(f"EXTRACTED TOOLS: {tool_names}")
                    return tool_names
                except Exception as e:
                    log_debug(f"TOOLS EXTRACTION ERROR: {e}")
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
            log_student(f"LDAI WORKFLOW ERROR: {e}")
            
            # Return error response
            return ChatResponse(
                id=str(uuid.uuid4()),
                response=f"I apologize, but I encountered an error processing your request: {e}",
                tool_calls=[],
                variation_key="error",
                model="error",
                agent_configurations=[]
            )