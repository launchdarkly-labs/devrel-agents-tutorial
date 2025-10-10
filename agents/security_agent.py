from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain.chat_models import init_chat_model
from config_manager import FixedConfigManager as ConfigManager
from pydantic import BaseModel
from utils.logger import log_student

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
    
    # Clear cache to ensure latest config
    config_manager.clear_cache()
    
    # NOTE: Model will be created at runtime with fresh LaunchDarkly config
    
    
    # NOTE: Instructions are fetched on each call using LaunchDarkly pattern

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

            # Fetch config dynamically for each call
            # Get latest config from LaunchDarkly
            user_context = state.get("user_context", {})
            user_id = state.get("user_id", "security_user")

            agent_config = await config_manager.get_config(
                user_id=user_id,
                config_key="security-agent",
                user_context=user_context
            )

            if not agent_config.enabled:
                # Return safe default if config is disabled
                return {
                    "messages": [AIMessage(content="PII Analysis: detected=false, types=[]")],
                    "detected": False,
                    "types": [],
                    "redacted": state["messages"][0].content if state["messages"] else "",
                    "response": "Security check disabled"
                }

            # Create model with structured output and up-to-date instructions
            from config_manager import map_provider_to_langchain
            langchain_provider = map_provider_to_langchain(agent_config.provider.name)

            base_model = init_chat_model(
                model=agent_config.model.name,
                model_provider=langchain_provider,
                temperature=0.0
            )

            # Use structured output for guaranteed PII format
            # include_raw=True preserves usage metadata for cost tracking
            structured_model = base_model.with_structured_output(PIIDetectionResponse, include_raw=True)

            # Create system message with current instructions from LaunchDarkly
            system_message = SystemMessage(content=agent_config.instructions)
            full_messages = [system_message] + messages

            # Apply rate limiting before LLM call
            from agents.ld_agent_helpers import _rate_limit_llm_call
            _rate_limit_llm_call()

            # Call model with structured output
            if hasattr(structured_model, "ainvoke"):
                response = await structured_model.ainvoke(full_messages)
            else:
                response = structured_model.invoke(full_messages)
            
            # Extract parsed result from response
            pii_result = response["parsed"] if isinstance(response, dict) else response
            
            # Extract and track token usage from raw response
            if isinstance(response, dict) and "raw" in response and hasattr(response["raw"], "usage_metadata"):
                usage_data = response["raw"].usage_metadata
                if usage_data:
                    from ldai.tracker import TokenUsage
                    token_usage = TokenUsage(
                        input=usage_data.get("input_tokens", 0),
                        output=usage_data.get("output_tokens", 0),
                        total=usage_data.get("total_tokens", 0)
                    )
                    agent_config.tracker.track_tokens(token_usage)
                    log_student(f"SECURITY PII DETECTION TOKENS: {token_usage.total} tokens ({token_usage.input} in, {token_usage.output} out)")

                    # Track cost metric with AI Config metadata for experiment attribution
                    from utils.cost_calculator import calculate_cost
                    cost = calculate_cost(agent_config.model.name, token_usage.input, token_usage.output)
                    if cost > 0:
                        # Use centralized context builder to ensure exact match with AI Config evaluation
                        user_id = state.get("user_id", "security_user")
                        user_context_data = state.get("user_context", {})
                        ld_context = config_manager.build_context(user_id, user_context_data)

                        # Track cost with metadata for experiment attribution
                        config_manager.track_cost_metric(agent_config, ld_context, cost, "security-agent")
                        log_student(f"COST TRACKING: ${cost:.6f} for {agent_config.model.name}")

            # Track success metric
            agent_config.tracker.track_success()

            # Extract structured results
            detected = pii_result.detected
            types = pii_result.types
            redacted_text = pii_result.redacted

            # Store structured results in state and create AI message for conversation flow
            response_message = AIMessage(content=f"PII Analysis: detected={detected}, types={types}")

            return {
                "messages": [response_message],
                "detected": detected,
                "types": types,
                "redacted": redacted_text,
                "response": f"PII Analysis: detected={detected}, types={types}"
            }
            
        except Exception as e:
            
            # Track error with LDAI metrics
            try:
                if 'agent_config' in locals() and agent_config and hasattr(agent_config, 'tracker'):
                    agent_config.tracker.track_error()
            except:
                pass
            
            error_response = AIMessage(content="Security processing encountered an error.")
            return {
                "messages": [error_response],
                "detected": False,
                "types": [],
                "redacted": state.get("user_input", "")
            }
    
    
    def format_final_response(state: AgentState):
        """Format the final security agent response"""
        messages = state["messages"]
        
        # Get final response from last AI message
        final_message = None
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                final_message = message
                break
        
        if final_message:
            final_response = final_message.content
        else:
            final_response = "Security processing completed."
        
        # Get PII results from state (set directly by call_model with structured output)
        pii_detected = state.get("detected", False)
        pii_types = state.get("types", [])
        redacted_text = state.get("redacted", state.get("user_input", ""))
        
        if pii_detected:
            pii_summary = f"Found {', '.join(pii_types)}" if pii_types else "Sensitive data detected"
            log_student(f"SECURITY: {pii_summary} → Sanitized")
        else:
            log_student(f"SECURITY: Clean - No PII detected")
        
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

    # Note: No conditional routing needed - security agent has simple linear flow
    
    return workflow.compile()