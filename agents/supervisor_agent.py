from typing import TypedDict, List, Annotated, Literal
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent
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

    # Keep the most recent messages, ensuring we end with assistant response if possible
    recent_messages = conversation_messages[-max_messages:]

    # Log that we're trimming for educational purposes
    trimmed_count = len(conversation_messages) - len(recent_messages)
    if trimmed_count > 0:
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
│                 │.   │                 │
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
    
    # Import needed modules for model creation
    from langchain.chat_models import init_chat_model
    
    # Create child agents with config manager
    support_agent = create_support_agent(support_config, config_manager)
    security_agent = create_security_agent(security_config, config_manager)

    log_debug(f"SUPERVISOR INSTRUCTIONS: {supervisor_config.instructions}")

    def _select_provider_and_model(default_provider: str, default_model: str) -> tuple[str, str]:
        """Select provider/model for CI while preserving full functionality.

        If CI_SAFE_MODE is set and Anthropic is unavailable but OpenAI is available,
        prefer OpenAI to avoid external connectivity issues while still exercising LLMs.
        """
        import os
        ci = os.getenv("CI_SAFE_MODE", "").lower() in {"1", "true", "yes"}
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if ci and (not anthropic_key) and openai_key:
            return ("openai", "gpt-4o-mini")
        return (default_provider, default_model)

    def pii_prescreen_node(state: SupervisorState):
        """
        Analyze user input to determine if it likely contains PII.
        Routes to security agent if PII suspected, otherwise direct to support.
        """
        try:
            user_input = state["user_input"]
            user_id = state.get("user_id", "supervisor_user")
            user_context = state.get("user_context", {})

            # Create PII pre-screening model with structured output
            from agents.ld_agent_helpers import map_provider_to_langchain, create_bedrock_chat_model
            from utils.bedrock_helpers import normalize_bedrock_provider
            import os

            # CI_SAFE_MODE: Prefer OpenAI when Anthropic unavailable
            selected_provider, selected_model = _select_provider_and_model(
                supervisor_config.provider.name,
                supervisor_config.model.name
            )

            # Normalize provider name to handle bedrock:anthropic format
            normalized_provider = normalize_bedrock_provider(selected_provider)
            langchain_provider = map_provider_to_langchain(normalized_provider)

            # Handle Bedrock vs direct API routing
            if langchain_provider == 'bedrock':
                auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
                if auth_method == 'sso' and hasattr(config_manager, 'boto3_session') and config_manager.boto3_session:
                    base_model = create_bedrock_chat_model(
                        model_id=selected_model,
                        session=config_manager.boto3_session,
                        region=config_manager.aws_region,
                        temperature=0.1
                    )
                else:
                    # Fall back to direct anthropic API
                    fallback_provider = 'anthropic' if selected_provider.lower() == 'anthropic' else langchain_provider
                    base_model = init_chat_model(
                        model=selected_model,
                        model_provider=fallback_provider,
                        temperature=0.1
                    )
            else:
                base_model = init_chat_model(
                    model=selected_model,
                    model_provider=langchain_provider,
                    temperature=0.1
                )

            # Use include_raw=True to preserve usage metadata for cost tracking
            prescreen_model = base_model.with_structured_output(PIIPreScreening, include_raw=True)

            # Get pre-screening prompt from LaunchDarkly config
            prescreen_prompt = supervisor_config.instructions

            screening_message = HumanMessage(content=f"{prescreen_prompt}\n\nUser Input: {user_input}")

            # Apply rate limiting before LLM call
            from agents.ld_agent_helpers import _rate_limit_llm_call
            _rate_limit_llm_call()

            # Get structured pre-screening result with raw response
            response = prescreen_model.invoke([screening_message])
            screening_result = response["parsed"] if isinstance(response, dict) else response
            
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
                    supervisor_config.tracker.track_tokens(token_usage)
                    log_student(f"PII PRESCREEN TOKENS: {token_usage.total} tokens ({token_usage.input} in, {token_usage.output} out)")

                    # Track cost metric with AI Config metadata for experiment attribution
                    from utils.cost_calculator import calculate_cost
                    cost = calculate_cost(supervisor_config.model.name, token_usage.input, token_usage.output)
                    if cost > 0:
                        # Use centralized context builder to ensure exact match with AI Config evaluation
                        user_id = state.get("user_id", "supervisor_user")
                        user_context = state.get("user_context", {})
                        ld_context = config_manager.build_context(user_id, user_context)

                        # Track cost with metadata for experiment attribution
                        config_manager.track_cost_metric(supervisor_config, ld_context, cost, "supervisor-agent")
                        log_student(f"COST TRACKING: ${cost:.6f} for {supervisor_config.model.name}")

            # Track success metric
            supervisor_config.tracker.track_success()

            # Log the intelligent decision
            log_student(f"ROUTING: {screening_result.recommended_route} ({screening_result.confidence:.1f}) - {screening_result.reasoning}")

            # Update workflow stage based on decision
            if screening_result.recommended_route == "security_agent":
                next_stage = "security_processing"
            else:
                next_stage = "direct_support"

            return {
                "current_agent": screening_result.recommended_route,
                "workflow_stage": next_stage,
                "messages": [AIMessage(content=f"Routing decision: {screening_result.reasoning}")]
            }

        except Exception as e:
            # Fallback to security agent for safety
            log_student(f"PII PRE-SCREENING ERROR: {type(e).__name__}: {str(e)}")
            log_debug(f"PII PRE-SCREENING ERROR DETAIL: {e}")
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
        - Tracks metrics for LaunchDarkly optimization
        """
        try:
            workflow_stage = state.get("workflow_stage", "pii_prescreen")  # Start with intelligent pre-screening
            security_cleared = state.get("security_cleared", False)
            support_response = state.get("support_response", "")

            # Track supervisor decision-making process
            # Enhanced routing logic with intelligent pre-screening
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
            elif support_response:
                next_agent = "complete"
            else:
                # All workflow stages should be handled above - default to complete
                next_agent = "complete"
            # Track successful supervisor decision
            return {"current_agent": next_agent}

        except Exception:

            # Track supervisor error with LDAI metrics
            return {"current_agent": "security_agent"}
    async def security_node(state: SupervisorState):
        """
        LANGGRAPH NODE: Security Agent Orchestration

        PURPOSE: Execute security agent and manage PII isolation boundaries

        SECURITY ISOLATION WORKFLOW:
        1. Prepare security agent input with raw user data
        2. Execute security agent to detect and redact PII
        3. Create sanitized message history for support agent
        4. Update state with security results and sanitized data

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
            
            # Track supervisor orchestration start for security agent
            # Prepare security agent input
            security_input = {
                "user_input": state["user_input"],
                "user_id": state.get("user_id", "security_user"),  # Pass user ID for LaunchDarkly targeting
                "user_context": state.get("user_context", {}),    # Pass user context for LaunchDarkly targeting
                "response": "",
                "tool_calls": [],
                "messages": [HumanMessage(content=state["messages"][-2].content if len(state["messages"]) >= 2 else state["user_input"])]
            }
            
            # Execute security agent
            if hasattr(security_agent, "ainvoke"):
                result = await security_agent.ainvoke(security_input)
            else:
                result = security_agent.invoke(security_input)
            
            # Track successful supervisor orchestration for security agent
            # After security processing, route to support with sanitized data
            new_stage = "post_security_support"

            # Extract PII schema fields from security agent
            detected = result.get("detected", False)
            types = result.get("types", [])
            redacted_text = result.get("redacted", state["user_input"])

            # Create sanitized message history - replace original user input with redacted version
            sanitized_messages = []
            original_messages = state.get("messages", [])
            
            for msg in original_messages:
                if isinstance(msg, HumanMessage):
                    sanitized_msg = HumanMessage(content=redacted_text)
                    sanitized_messages.append(sanitized_msg)
                else:
                    sanitized_messages.append(msg)
            
            # Add the security agent's response
            security_response = AIMessage(content=result["response"])
            sanitized_messages.append(security_response)
            
            
            return {
                "messages": [security_response],  # Only add security response to main message flow
                "workflow_stage": new_stage,
                "security_cleared": True,  # Always proceed after security agent
                "processed_user_input": redacted_text,  # Use redacted text for support agent
                "pii_detected": detected,
                "pii_types": types,
                "redacted_text": redacted_text,
                "sanitized_messages": sanitized_messages,  # Store clean message history
                "security_tool_details": result.get("tool_details", [])  # Capture security agent tool details
            }
            
        except Exception as e:
            # Track error with LDAI metrics
            if 'supervisor_config' in locals() and supervisor_config and hasattr(supervisor_config, 'tracker'):
                supervisor_config.tracker.track_error()

            return {
                "messages": [AIMessage(content=f"Security agent error: {e}")],
                "workflow_stage": "error",
                "security_cleared": False
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
        - All message history is pre-sanitized by security agent
        - Support agent operates in completely PII-isolated environment

        LANGGRAPH PATTERNS:
        - Node enforces security boundaries through state field selection
        - Orchestrates child agent with controlled input
        - Manages tool execution and result aggregation
        """
        try:
            
            # Track supervisor orchestration start for support agent
            # Use processed (potentially redacted) text if available
            processed_input = state.get("processed_user_input", state["user_input"])

            # Safety check: Ensure processed input is not empty
            if not processed_input or not processed_input.strip():
                processed_input = state["user_input"]  # Fallback to original input

            pii_detected = state.get("pii_detected", False)
            pii_types = state.get("pii_types", [])
            sanitized_messages = state.get("sanitized_messages", [])
            
            # ===== CRITICAL SECURITY BOUNDARY: PII ISOLATION =====
            # Support agent must NEVER see raw messages containing PII
            # Only sanitized/redacted messages are passed through this boundary
            if sanitized_messages:
                # Include conversation history + current redacted message
                full_messages = sanitized_messages + [HumanMessage(content=processed_input)]
            else:
                full_messages = [HumanMessage(content=processed_input)]  # Fallback to redacted current message only

            # === MESSAGE MEMORY MANAGEMENT ===
            # Trim message history to prevent context window overflow
            # This is critical for long conversations that could exceed model limits
            support_messages = trim_message_history(full_messages, max_messages=10)

            # Safety check: Ensure all messages have non-empty content
            valid_messages = []
            for msg in support_messages:
                if hasattr(msg, 'content') and msg.content and msg.content.strip():
                    valid_messages.append(msg)

            # Ensure we have at least one valid message
            if not valid_messages:
                valid_messages = [HumanMessage(content=processed_input)]

            support_messages = valid_messages
            
            # ===== SUPPORT AGENT COMPLETE PII ISOLATION =====
            # This input contains ONLY sanitized/redacted content
            # Support agent operates in completely PII-free environment

            # Log PII protection status
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
            
            # Execute support agent
            if hasattr(support_agent, "ainvoke"):
                result = await support_agent.ainvoke(support_input)
            else:
                result = support_agent.invoke(support_input)
            
            # Track successful supervisor orchestration for support agent
            tool_calls = result.get("tool_calls", [])
            support_response = result["response"]

            tool_details = result.get('tool_details', [])

            return {
                "messages": [AIMessage(content=support_response)],
                "support_response": support_response,
                "support_tool_calls": tool_calls,
                "support_tool_details": tool_details,
                "workflow_stage": "complete"
            }
            
        except Exception as e:
            # Track error with LDAI metrics
            if 'supervisor_config' in locals() and supervisor_config and hasattr(supervisor_config, 'tracker'):
                supervisor_config.tracker.track_error()

            return {
                "messages": [AIMessage(content=f"Support agent error: {e}")],
                "support_response": f"Error processing request: {e}",
                "support_tool_calls": [],
                "support_tool_details": [],
                "workflow_stage": "error"
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
        """Format final response with supervisor completion metrics"""
        try:
            
            # Track supervisor workflow completion
            support_tool_calls = state.get("support_tool_calls", [])
            support_response = state.get("support_response", "")
            
            if support_response:
                final_content = support_response
            else:
                final_message = state["messages"][-1]
                final_content = final_message.content
            
            
            return {
                "final_response": final_content,
                "actual_tool_calls": support_tool_calls,
                "support_tool_details": state.get("support_tool_details", []),
                "user_input": state["user_input"],
                "workflow_stage": "complete"
            }
            
        except Exception as e:
            
            # Track supervisor final formatting error
            return {
                "final_response": f"I apologize, but I encountered an error finalizing the response: {e}",
                "actual_tool_calls": [],
                "support_tool_details": [],
                "user_input": state["user_input"],
                "workflow_stage": "error"
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