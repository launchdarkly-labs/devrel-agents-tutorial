from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from config_manager import FixedConfigManager as ConfigManager
from pydantic import BaseModel
from utils.logger import log_student
from .ld_agent_helpers import create_chat_model, ci_safe_provider_and_model, _rate_limit_llm_call

WITHHELD_MESSAGE = "[Message withheld: the security check failed]"

class PIIDetectionResponse(BaseModel):
    """Structured response for PII detection results"""
    detected: bool
    types: List[str]
    redacted: str

class AgentState(TypedDict):
    """
    LangGraph State for Security Agent Workflow

    This agent implements a simple linear workflow: call_model → format_response
    The key pattern is using structured output (Pydantic) for reliable PII detection.

    PII DETECTION SCHEMA FIELDS (returned to supervisor):
    - detected: boolean indicating if any PII was found
    - types: list of PII types found ["email", "phone", "ssn", etc.]
    - redacted: sanitized version of user input with PII replaced
    """

    # === CORE MESSAGE FLOW ===
    messages: Annotated[List[BaseMessage], add_messages]  # LangGraph message history
    user_input: str  # Raw user input (may contain PII)
    response: str  # Security agent's analysis response

    # === LAUNCHDARKLY TARGETING ===
    user_id: str  # For LaunchDarkly configuration targeting
    user_context: dict  # For LaunchDarkly configuration targeting

    # === TOOL EXECUTION (unused by security agent) ===
    tool_calls: List[str]  # Tool names (security agent doesn't use tools)
    tool_details: List[dict]  # Tool details (security agent doesn't use tools)

    # === PII DETECTION RESULTS ===
    # These fields match the PIIDetectionResponse Pydantic model
    detected: bool  # True if PII found in user input
    types: List[str]  # Types of PII detected: ["email", "phone", "ssn"]
    redacted: str  # User input with PII replaced by placeholders

def create_security_agent(agent_config, config_manager: ConfigManager):
    """
    Create Security Agent with Structured PII Detection

    LANGGRAPH WORKFLOW: call_model → format_final_response

    KEY PATTERNS DEMONSTRATED:
    - Structured output using Pydantic models for reliable parsing
    - Dynamic configuration fetching from LaunchDarkly
    - Simple linear workflow (no conditional routing needed)
    - State management for PII detection results

    SECURITY APPROACH:
    - Uses native LLM PII detection capabilities
    - Returns structured results (detected, types, redacted)
    - No external tools required for PII detection
    """
    # NOTE: Model and instructions are fetched on each call from LaunchDarkly

    async def call_model(state: AgentState):
        """
        LANGGRAPH NODE: PII Detection with Structured Output

        PURPOSE: Detect and redact PII using native LLM capabilities

        WORKFLOW:
        1. Fetch latest LaunchDarkly configuration
        2. Create LLM with structured output (Pydantic model)
        3. Analyze user input for PII
        4. Return structured results: detected, types, redacted

        LANGGRAPH PATTERNS:
        - Node function receives and returns state dict
        - Uses structured output for guaranteed parsing reliability
        - Dynamic configuration fetching within node function
        - Error handling with safe fallbacks
        """
        try:
            messages = state["messages"]

            user_context = state.get("user_context", {})
            user_id = state.get("user_id", "security_user")

            served = agent_config or await config_manager.get_config(
                user_id=user_id,
                config_key="security-agent",
                user_context=user_context
            )

            # Create model with structured output and up-to-date instructions
            provider, model = ci_safe_provider_and_model(served.provider_name, served.model_name)
            base_model = create_chat_model(provider, model, config_manager, served.parameters)
            log_student(f"SECURITY ROUTING: Using {provider} for {model}")

            # Use structured output for guaranteed PII format
            # include_raw=True keeps the usage metadata that token and cost tracking need
            structured_model = base_model.with_structured_output(PIIDetectionResponse, include_raw=True)

            # Apply rate limiting before LLM call
            _rate_limit_llm_call()

            async def run_security(_tools=None, variables=None):
                system_message = SystemMessage(content=served.render_instructions(variables))
                response = await structured_model.ainvoke([system_message] + messages)
                if response["parsed"] is None:
                    raise ValueError(f"{model} returned no structured PII result; use a model that supports structured output")
                parsed = response["parsed"]
                return parsed, parsed.model_dump_json(), response["raw"].usage_metadata

            ld_context = config_manager.build_context(user_id, user_context)
            pii_result = await config_manager.track(served, ld_context, run_security, state.get("user_input"))

            # Store structured results in state and create AI message for conversation flow
            summary = f"PII Analysis: detected={pii_result.detected}, types={pii_result.types}"

            return {
                "messages": [AIMessage(content=summary)],
                "detected": pii_result.detected,
                "types": pii_result.types,
                "redacted": pii_result.redacted,
                "response": summary
            }

        except Exception as e:
            log_student(f"SECURITY ERROR: {e}")

            # Fail closed: an unchecked message may contain PII, so it never reaches the support agent.
            error_response = AIMessage(content="Security processing encountered an error.")
            return {
                "messages": [error_response],
                "detected": False,
                "types": [],
                "redacted": WITHHELD_MESSAGE
            }


    def format_final_response(state: AgentState):
        """Format the final security agent response"""
        messages = state["messages"]

        # Get final response from last AI message
        final_response = next(
            (m.content for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            "Security processing completed."
        )

        # Get PII results from state (set directly by call_model with structured output)
        pii_detected = state.get("detected", False)
        pii_types = state.get("types", [])
        # An empty redaction must not fall back to the raw input, which may contain PII
        redacted_text = state.get("redacted") or WITHHELD_MESSAGE

        if pii_detected:
            pii_summary = f"Found {', '.join(pii_types)}" if pii_types else "Sensitive data detected"
            log_student(f"SECURITY: {pii_summary} → Sanitized")
        else:
            log_student("SECURITY: Clean - No PII detected")

        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": [],
            "tool_details": [],
            "messages": messages,
            # Return the exact PII schema fields for supervisor and UI
            "detected": pii_detected,
            "types": pii_types,
            "redacted": redacted_text
        }

    # =============================================
    # LANGGRAPH WORKFLOW CONSTRUCTION
    # =============================================

    # Build simple linear workflow: call_model → format_final_response
    workflow = StateGraph(AgentState)

    # === ADD NODES ===
    workflow.add_node("call_model", call_model)              # PII detection with structured output
    workflow.add_node("format", format_final_response)       # Format results for supervisor

    # === LINEAR WORKFLOW ===
    workflow.set_entry_point("call_model")                   # Start with PII detection
    workflow.add_edge("call_model", "format")                # Always go to formatting
    workflow.set_finish_point("format")                      # End with formatted results

    return workflow.compile()
