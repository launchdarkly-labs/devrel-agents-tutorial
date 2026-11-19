import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage
from launchdarkly_ai_server import conversation_id
from opentelemetry import trace
from ..models import ChatResponse, AgentConfig as APIAgentConfig
from agents.supervisor_agent import create_supervisor_agent, trim_message_history
from config_manager import FixedConfigManager as ConfigManager, TRACER_NAME
from utils.logger import log_student, log_debug

MAX_MESSAGE_LENGTH = 5000

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

            # Validate inputs
            if len(message) > MAX_MESSAGE_LENGTH:
                return ChatResponse(
                    id=str(uuid.uuid4()),
                    response=f"Message too long ({len(message)} characters). Please limit to {MAX_MESSAGE_LENGTH} characters.",
                    tool_calls=[],
                    variation_key="validation_error",
                    model="validation_error",
                    agent_configurations=[]
                )
            user_id = user_id.strip() or "anonymous_user"
            user_context = user_context or {}

            # Get LaunchDarkly LDAI configurations for all agents (initializes OTel tracer provider on first call)
            supervisor_config = await self.config_manager.get_config(user_id, "supervisor-agent", user_context)
            support_config = await self.config_manager.get_config(user_id, "support-agent", user_context)
            security_config = await self.config_manager.get_config(user_id, "security-agent", user_context)

            log_student("LDAI: 3 agents configured")
            log_debug(f"LDAI: Supervisor({supervisor_config.model_name}), Support({support_config.model_name}), Security({security_config.model_name})")

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
            for msg in sanitized_conversation_history or []:
                role = msg.get("role")
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                if role == "user":
                    sanitized_langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    sanitized_langchain_messages.append(AIMessage(content=content))

            # === MESSAGE MEMORY MANAGEMENT ===
            # Trim conversation history to prevent context overflow
            # This is especially important for long-running conversations
            sanitized_langchain_messages = trim_message_history(sanitized_langchain_messages, max_messages=8)

            # =============================================
            # LANGGRAPH INITIAL STATE CONSTRUCTION
            # =============================================

            # Create initial state for LangGraph workflow
            # This state object will flow through all agents
            initial_state = {
                # === CORE MESSAGE FLOW ===
                "user_input": message.strip(),                  # Raw message (security agent only) - trimmed
                "messages": [HumanMessage(content=message)],    # Security agent gets raw message
                "final_response": "",

                # === LAUNCHDARKLY TARGETING ===
                "user_id": user_id,
                "user_context": user_context,

                # === WORKFLOW ORCHESTRATION ===
                "current_agent": "",                            # Supervisor will determine first agent
                "workflow_stage": "pii_prescreen",              # Start with intelligent PII pre-screening
                "security_cleared": False,

                # === SUPPORT AGENT RESULTS ===
                "support_response": "",
                "support_tool_calls": [],
                "support_tool_details": [],

                # === PII SECURITY BOUNDARY ===
                "sanitized_messages": sanitized_langchain_messages,  # SUPPORT AGENT ONLY gets these
                "processed_user_input": "",                     # Will be set by security agent
                "pii_detected": False,                          # Will be set by security agent
                "pii_types": [],                                # Will be set by security agent
                "redacted_text": message.strip(),               # Will be updated by security agent
            }

            # =============================================
            # LANGGRAPH WORKFLOW EXECUTION (WITH OTEL ROOT TRACE)
            # =============================================

            log_student("INTELLIGENT ROUTING: Starting PII pre-screening analysis")

            tracer = trace.get_tracer(TRACER_NAME)
            trace_id_hex = None
            span_id_hex = None
            trace_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            with conversation_id(user_id), tracer.start_as_current_span("multi-agent-chat") as root_span:
                root_span.set_attribute("launchdarkly.operation.type", "gen_ai")
                root_span.set_attribute("context.contextKeys.user", user_id)
                span_ctx = root_span.get_span_context()
                if span_ctx and span_ctx.trace_id:
                    trace_id_hex = format(span_ctx.trace_id, "032x")
                    span_id_hex = format(span_ctx.span_id, "016x")
                result = await supervisor_agent.ainvoke(initial_state)

            if hasattr(self.config_manager, "flush_traces"):
                self.config_manager.flush_traces()

            actual_tool_calls = result.get("support_tool_calls", [])
            security_detected = result.get("pii_detected", False)

            log_student(f"WORKFLOW COMPLETE: PII detected: {security_detected}")

            def get_tools_list(ai_config):
                return [tool.get('name', 'unknown') for tool in ai_config.parameters.get('tools', [])]

            # Create agent configuration metadata showing actual usage
            agent_configurations = [
                APIAgentConfig(
                    agent_name="supervisor-agent",
                    variation_key=supervisor_config.variation_key,
                    model=supervisor_config.model_name,
                    tools=[],  # Supervisor doesn't have tools available
                    tools_used=[]  # Supervisor doesn't use tools directly
                ),
                APIAgentConfig(
                    agent_name="security-agent",
                    variation_key=security_config.variation_key,
                    model=security_config.model_name,
                    tools=get_tools_list(security_config),
                    tools_used=[],
                    tool_details=[],
                    # Pass PII detection results to UI
                    detected=security_detected,
                    types=result.get("pii_types", []),
                    redacted=result.get("redacted_text", message)
                ),
                APIAgentConfig(
                    agent_name="support-agent",
                    variation_key=support_config.variation_key,
                    model=support_config.model_name,
                    tools=get_tools_list(support_config),  # Show configured tools from LaunchDarkly
                    tools_used=actual_tool_calls,  # Show actual tools executed
                    tool_details=result.get("support_tool_details", [])  # Show detailed tool info with search queries
                )
            ]

            return ChatResponse(
                id=str(uuid.uuid4()),
                response=result["final_response"],
                tool_calls=actual_tool_calls,  # Show actual tools used
                variation_key=supervisor_config.variation_key,  # Use actual LaunchDarkly variation
                model=supervisor_config.model_name,  # Primary model
                trace_id=trace_id_hex,
                span_id=span_id_hex,
                trace_timestamp=trace_timestamp,
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
