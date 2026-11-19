from typing import TypedDict, List, Annotated, Literal
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent, WITHHELD_MESSAGE
from .ld_agent_helpers import create_chat_model, ci_safe_provider_and_model, _rate_limit_llm_call
from config_manager import FixedConfigManager as ConfigManager
from utils.logger import log_student, log_debug
from pydantic import BaseModel

def trim_message_history(messages: List[BaseMessage], max_messages: int = 10) -> List[BaseMessage]:
    """
    Trim message history to prevent context window overflow.
    Preserves system messages and keeps the most recent conversation messages.
    """
    if not messages:
        return messages

    # Separate system messages from conversation messages
    system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
    conversation_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    # If we're under the limit, return all messages
    if len(conversation_messages) <= max_messages:
        return system_messages + conversation_messages

    # Handle zero limit case
    if max_messages <= 0:
        if conversation_messages:
            log_student(f"MEMORY MANAGEMENT: Trimmed all {len(conversation_messages)} conversation messages, keeping only {len(system_messages)} system messages")
        return system_messages

    # Keep the most recent messages
    recent_messages = conversation_messages[-max_messages:]

    # Log that we're trimming for educational purposes
    trimmed_count = len(conversation_messages) - len(recent_messages)
    log_student(f"MEMORY MANAGEMENT: Trimmed {trimmed_count} old messages, keeping {len(recent_messages)} recent + {len(system_messages)} system messages")

    return system_messages + recent_messages

class PIIPreScreening(BaseModel):
    """Structured response for PII pre-screening"""
    likely_contains_pii: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    recommended_route: str  # "security_agent" or "support_agent"

class SupervisorState(TypedDict):
    """
    LangGraph State for Multi-Agent Supervisor Workflow

    This TypedDict defines the state object that flows through the entire workflow.
    Each field tracks specific aspects of the multi-agent conversation process.

    WORKFLOW STAGES: pii_prescreen → security_processing → post_security_support → complete
    """

    # === CORE MESSAGE FLOW ===
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    final_response: str

    # LaunchDarkly targeting
    user_id: str
    user_context: dict

    # Workflow orchestration
    current_agent: str
    workflow_stage: str
    security_cleared: bool

    # Support agent results
    support_response: str
    support_tool_calls: List[str]
    support_tool_details: List[dict]

    # PII security boundary
    processed_user_input: str
    pii_detected: bool
    pii_types: List[str]
    redacted_text: str
    sanitized_messages: List[BaseMessage]

def create_supervisor_agent(supervisor_config, support_config, security_config, config_manager: ConfigManager):
    """
    Create supervisor agent using LDAI SDK pattern

    LANGGRAPH WORKFLOW OVERVIEW:
    ============================

┌─────────────────┐    ┌─────────────────┐
│   SUPERVISOR    │    │ SECURITY AGENT  │
│                 │───▶│                 │
│ Smart Analysis  │    │ PII Detection   │
└─────────────────┘    └─────────────────┘
          │                       │
          ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ SUPPORT AGENT   │    │ SUPPORT AGENT   │
│                 │    │                 │
│ Direct Route    │    │ Post-Security   │
│ (No PII)        │    │ (Sanitized)     │
└─────────────────┘    └─────────────────┘
           │                      │
           ▼                      ▼
┌─────────────────────────────────────────┐
│           FORMAT FINAL                  │
│      Combine Results & Respond          │
└─────────────────────────────────────────┘

    KEY LANGGRAPH PATTERNS DEMONSTRATED:
    - StateGraph with TypedDict state management
    - Conditional routing based on state fields
    - Multi-agent orchestration with state isolation
    - Security boundaries through state field management
    - Dynamic configuration via LaunchDarkly integration
    """
    # Create child agents with config manager
    support_agent = create_support_agent(support_config, config_manager)
    security_agent = create_security_agent(security_config, config_manager)

    log_debug(f"SUPERVISOR INSTRUCTIONS: {supervisor_config.instructions}")

    async def pii_prescreen_node(state: SupervisorState):
        """
        Analyze user input to determine if it likely contains PII.
        Routes to security agent if PII suspected, otherwise direct to support.
        """
        try:
            user_input = state["user_input"]
            user_id = state.get("user_id", "supervisor_user")
            user_context = state.get("user_context", {})

            # Create PII pre-screening model with structured output
            provider, model = ci_safe_provider_and_model(supervisor_config.provider_name, supervisor_config.model_name)
            base_model = create_chat_model(provider, model, config_manager, supervisor_config.parameters)

            # include_raw=True keeps the usage metadata that token and cost tracking need
            prescreen_model = base_model.with_structured_output(PIIPreScreening, include_raw=True)

            # Apply rate limiting before LLM call
            _rate_limit_llm_call()

            async def call_prescreen(_tools=None, variables=None):
                prescreen_prompt = supervisor_config.render_instructions(variables)
                screening_message = HumanMessage(content=f"{prescreen_prompt}\n\nUser Input: {user_input}")
                response = await prescreen_model.ainvoke([screening_message])
                if response["parsed"] is None:
                    raise ValueError(f"{model} returned no structured routing decision; use a model that supports structured output")
                parsed = response["parsed"]
                return parsed, parsed.recommended_route, response["raw"].usage_metadata

            ld_context = config_manager.build_context(user_id, user_context)
            screening_result = await config_manager.track(supervisor_config, ld_context, call_prescreen, user_input)

            # The reasoning can quote the PII, so only the route and confidence are logged
            log_student(f"ROUTING: {screening_result.recommended_route} ({screening_result.confidence:.1f})")

            # Update workflow stage based on decision
            if screening_result.recommended_route == "security_agent":
                next_stage = "security_processing"
            else:
                next_stage = "direct_support"

            return {
                "current_agent": screening_result.recommended_route,
                "workflow_stage": next_stage,
                # The reasoning can quote the PII, so only the route goes into the conversation
                "messages": [AIMessage(content=f"Routing decision: {screening_result.recommended_route}")]
            }

        except Exception as e:
            # Fallback to security agent for safety
            log_student(f"PII PRE-SCREENING ERROR: {type(e).__name__}: {str(e)}")
            log_student("FALLBACK: Defaulting to security agent for safety")
            return {
                "current_agent": "security_agent",
                "workflow_stage": "security_processing",
                "messages": [AIMessage(content="Pre-screening error, routing to security for safety")]
            }

    def supervisor_node(state: SupervisorState):
        """
        LANGGRAPH NODE: Central Supervisor Router

        PURPOSE: Orchestrate workflow by deciding which agent should process next

        WORKFLOW DECISION LOGIC:
        - pii_prescreen: Initial smart routing analysis
        - security_processing: Route to security agent for PII detection
        - direct_support: Route directly to support agent (bypass security)
        - post_security_support: Route to support with sanitized data
        - complete: All processing done, format final response

        LANGGRAPH PATTERNS:
        - Central orchestration node that doesn't do LLM processing
        - Uses state fields to make routing decisions
        - Returns minimal state updates (just routing info)
        """
        workflow_stage = state.get("workflow_stage", "pii_prescreen")  # Start with intelligent pre-screening
        security_cleared = state.get("security_cleared", False)
        support_response = state.get("support_response", "")

        if workflow_stage == "pii_prescreen":
            next_agent = "pii_prescreen"
        elif workflow_stage == "security_processing" and not security_cleared:
            next_agent = "security_agent"
        elif workflow_stage == "direct_support" and not support_response:
            next_agent = "support_agent"
            log_student("BYPASS: Direct to support (no PII detected)")
        elif workflow_stage == "post_security_support" and not support_response:
            next_agent = "support_agent"
            log_student("SECURED: Routing to support with sanitized data")
        else:
            # Support has answered, or an agent failed: format what we have
            next_agent = "complete"
        return {"current_agent": next_agent}

    async def security_node(state: SupervisorState):
        """
        LANGGRAPH NODE: Security Agent Orchestration

        PURPOSE: Execute security agent and manage PII isolation boundaries

        SECURITY ISOLATION WORKFLOW:
        1. Prepare security agent input with raw user data
        2. Execute security agent to detect and redact PII
        3. Update state with security results and the redacted text

        CRITICAL PII BOUNDARY:
        - Input: Raw user data (may contain PII)
        - Output: Sanitized data + PII metadata
        - Support agent will ONLY see sanitized data from this point forward

        LANGGRAPH PATTERNS:
        - Node orchestrates child agent execution
        - Manages state transformation (raw → sanitized)
        - Implements security boundaries through state field management
        """
        try:
            # Prepare security agent input
            security_input = {
                "user_input": state["user_input"],
                "user_id": state.get("user_id", "security_user"),  # Pass user ID for LaunchDarkly targeting
                "user_context": state.get("user_context", {}),    # Pass user context for LaunchDarkly targeting
                "response": "",
                "tool_calls": [],
                "messages": [HumanMessage(content=state["messages"][-2].content if len(state["messages"]) >= 2 else state["user_input"])]
            }

            result = await security_agent.ainvoke(security_input)

            # Extract PII schema fields from security agent
            detected = result.get("detected", False)
            types = result.get("types", [])
            # An empty redaction must not fall back to the raw input, which may contain PII
            redacted_text = result.get("redacted") or WITHHELD_MESSAGE

            security_response = AIMessage(content=result["response"])

            # sanitized_messages keeps the earlier, already redacted turns; the support node adds this one
            return {
                "messages": [security_response],  # Only add security response to main message flow
                "workflow_stage": "post_security_support",  # Route to support with sanitized data
                "security_cleared": True,  # Always proceed after security agent
                "processed_user_input": redacted_text,  # Use redacted text for support agent
                "pii_detected": detected,
                "pii_types": types,
                "redacted_text": redacted_text,
            }

        except Exception as e:
            # The failed agent already recorded its own generation error.
            return {
                "messages": [AIMessage(content=f"Security agent error: {e}")],
                "workflow_stage": "error",
                "security_cleared": False,
                # The UI saves redacted_text as history, so never leave the raw input there
                "redacted_text": WITHHELD_MESSAGE,
            }

    async def support_node(state: SupervisorState):
        """
        LANGGRAPH NODE: Support Agent Orchestration

        PURPOSE: Execute support agent with proper PII isolation

        PII PROTECTION WORKFLOW:
        1. Use processed/redacted user input (never raw input)
        2. Use sanitized message history (never raw messages)
        3. Execute support agent in PII-free environment
        4. Return tool results and response

        CRITICAL SECURITY BOUNDARY ENFORCEMENT:
        - Support agent NEVER sees raw user input containing PII
        - Message history only holds earlier turns that were already redacted
        - Support agent operates in completely PII-isolated environment

        LANGGRAPH PATTERNS:
        - Node enforces security boundaries through state field selection
        - Orchestrates child agent with controlled input
        - Manages tool execution and result aggregation
        """
        # Use the redacted text if the security agent ran; the original input only on the direct route
        if state.get("security_cleared"):
            processed_input = state.get("processed_user_input") or WITHHELD_MESSAGE
        else:
            processed_input = state["user_input"]

        pii_detected = state.get("pii_detected", False)
        pii_types = state.get("pii_types", [])

        # ===== CRITICAL SECURITY BOUNDARY: PII ISOLATION =====
        # Support agent must NEVER see raw messages containing PII
        # Only sanitized/redacted messages are passed through this boundary
        full_messages = state.get("sanitized_messages", []) + [HumanMessage(content=processed_input)]

        # === MESSAGE MEMORY MANAGEMENT ===
        # Trim message history to prevent context window overflow
        # This is critical for long conversations that could exceed model limits
        support_messages = trim_message_history(full_messages, max_messages=10)

        # Models reject messages with empty content
        support_messages = [msg for msg in support_messages if msg.content and msg.content.strip()]
        if not support_messages:
            support_messages = [HumanMessage(content=processed_input)]

        if pii_detected:
            log_student(f"PII PROTECTED: {', '.join(pii_types)} redacted")

        support_input = {
            "user_input": processed_input,  # Redacted text only
            "user_id": state.get("user_id", "support_user"),  # For LaunchDarkly context
            "user_context": state.get("user_context", {}),  # For LaunchDarkly targeting
            "response": "",
            "tool_calls": [],
            "tool_details": [],
            "messages": support_messages  # Sanitized conversation history only
        }

        # The support agent returns a friendly error response instead of raising
        result = await support_agent.ainvoke(support_input)

        return {
            "messages": [AIMessage(content=result["response"])],
            "support_response": result["response"],
            "support_tool_calls": result.get("tool_calls", []),
            "support_tool_details": result.get("tool_details", []),
            "workflow_stage": "complete"
        }

    def route_decision(state: SupervisorState) -> Literal["pii_prescreen", "security_agent", "support_agent", "complete"]:
        """
        LANGGRAPH CONDITIONAL ROUTING FUNCTION

        PURPOSE: Determine next node based on current state

        ROUTING LOGIC:
        - "pii_prescreen": Route to intelligent pre-screening
        - "security_agent": Route to security agent for PII detection
        - "support_agent": Route to support agent (direct or post-security)
        - "complete": Workflow finished, route to final formatting

        LANGGRAPH PATTERNS:
        - Conditional routing function returns string node names
        - Uses state fields to make routing decisions
        - Must return one of the defined edge targets
        - Simple logic based on current_agent state field
        """
        current_agent = state.get("current_agent", "pii_prescreen")

        if "pii_prescreen" in current_agent:
            return "pii_prescreen"
        elif "security" in current_agent:
            return "security_agent"
        elif "support" in current_agent:
            return "support_agent"
        else:
            return "complete"

    def format_final(state: SupervisorState):
        """Use the support agent's answer, or the last message if an agent failed"""
        final_content = state.get("support_response") or state["messages"][-1].content
        return {
            "final_response": final_content,
            "workflow_stage": "complete"
        }

    # =============================================
    # LANGGRAPH WORKFLOW CONSTRUCTION
    # =============================================

    # Build intelligent supervisor workflow using LangGraph StateGraph
    workflow = StateGraph(SupervisorState)

    # === ADD NODES ===
    # Each node is a function that receives and returns state
    workflow.add_node("supervisor", supervisor_node)       # Central orchestrator
    workflow.add_node("pii_prescreen", pii_prescreen_node) # Intelligent pre-screening
    workflow.add_node("security_agent", security_node)     # PII detection & redaction
    workflow.add_node("support_agent", support_node)       # Tool execution & response
    workflow.add_node("format_final", format_final)        # Final response formatting

    # === SET ENTRY POINT ===
    # Workflow always starts with supervisor for routing
    workflow.set_entry_point("supervisor")

    # === CONDITIONAL ROUTING ===
    # Supervisor routes to different nodes based on state
    workflow.add_conditional_edges(
        "supervisor",                # From supervisor node
        route_decision,             # Using this routing function
        {                           # Route to these nodes:
            "pii_prescreen": "pii_prescreen",      # Smart pre-screening
            "security_agent": "security_agent",    # PII detection
            "support_agent": "support_agent",      # Tool execution
            "complete": "format_final"             # Final formatting
        }
    )

    # === LINEAR EDGES ===
    # After processing, agents return to supervisor for next routing decision
    workflow.add_edge("pii_prescreen", "supervisor")  # Pre-screening → supervisor
    workflow.add_edge("security_agent", "supervisor") # Security → supervisor
    workflow.add_edge("support_agent", "supervisor")  # Support → supervisor

    # === SET FINISH POINT ===
    # Workflow ends at format_final node
    workflow.set_finish_point("format_final")

    return workflow.compile()
