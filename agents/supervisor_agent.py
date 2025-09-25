from typing import TypedDict, List, Annotated, Literal
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent
from config_manager import FixedConfigManager as ConfigManager
from utils.logger import log_student
from pydantic import BaseModel

class PIIPreScreening(BaseModel):
    """Structured response for PII pre-screening"""
    likely_contains_pii: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    recommended_route: str  # "security_agent" or "support_agent"

class SupervisorState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    user_id: str  # User ID for LaunchDarkly context
    user_context: dict  # User context for LaunchDarkly targeting
    current_agent: str
    security_cleared: bool
    support_response: str
    support_tool_calls: List[str]
    support_tool_details: List[dict]
    final_response: str
    workflow_stage: str
    processed_user_input: str  # Redacted text from security agent
    pii_detected: bool  # PII schema field from security agent
    pii_types: List[str]  # PII schema field from security agent
    redacted_text: str  # PII schema field from security agent
    sanitized_messages: List[BaseMessage]  # Clean message history without PII

def create_supervisor_agent(supervisor_config, support_config, security_config, config_manager: ConfigManager):
    """Create supervisor agent using LDAI SDK pattern"""
    
    # Import needed modules for model creation
    from langchain.chat_models import init_chat_model
    from config_manager import map_provider_to_langchain
    
    # Create child agents with config manager
    support_agent = create_support_agent(support_config, config_manager)
    security_agent = create_security_agent(security_config, config_manager)
    
    log_student(f"🎯 SUPERVISOR INSTRUCTIONS: {supervisor_config.instructions}")

    def pii_prescreen_node(state: SupervisorState):
        """Intelligent PII pre-screening to route requests efficiently"""
        try:
            user_input = state["user_input"]
            user_id = state.get("user_id", "supervisor_user")
            user_context = state.get("user_context", {})

            # Track PII pre-screening start
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_pii_prescreen_start"
            )

            # Create PII pre-screening model with structured output
            langchain_provider = map_provider_to_langchain(supervisor_config.provider.name)

            base_model = init_chat_model(
                model=supervisor_config.model.name,
                model_provider=langchain_provider,
                temperature=0.1
            )

            prescreen_model = base_model.with_structured_output(PIIPreScreening)

            # Get pre-screening prompt from LaunchDarkly config
            prescreen_prompt = supervisor_config.instructions

            screening_message = HumanMessage(content=f"{prescreen_prompt}\n\nUser Input: {user_input}")

            # Get structured pre-screening result
            screening_result = prescreen_model.invoke([screening_message])

            # Track successful pre-screening
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_pii_prescreen_success_{screening_result.recommended_route}"
            )

            # Log the intelligent decision
            log_student(f"🧠 ROUTING: {screening_result.recommended_route} ({screening_result.confidence:.1f}) - {screening_result.reasoning}")

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
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)
            )

            log_student(f"⚠️ PII PRE-SCREENING ERROR: Defaulting to security agent for safety")
            return {
                "current_agent": "security_agent",
                "workflow_stage": "security_processing",
                "messages": [AIMessage(content="Pre-screening error, routing to security for safety")]
            }

    def supervisor_node(state: SupervisorState):
        """Supervisor decides next step in workflow with LDAI metrics tracking"""
        try:
            messages = state["messages"]
            workflow_stage = state.get("workflow_stage", "pii_prescreen")  # Start with intelligent pre-screening
            security_cleared = state.get("security_cleared", False)
            support_response = state.get("support_response", "")

            # Track supervisor decision-making process
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_decision_start"
            )

            # Enhanced routing logic with intelligent pre-screening
            if workflow_stage == "pii_prescreen":
                next_agent = "pii_prescreen"
            elif workflow_stage == "security_processing" and not security_cleared:
                next_agent = "security_agent"
            elif workflow_stage == "direct_support" and not support_response:
                next_agent = "support_agent"
                log_student(f"🚀 BYPASS: Direct to support (no PII detected)")
            elif workflow_stage == "post_security_support" and not support_response:
                next_agent = "support_agent"
                log_student(f"🛡️ SECURED: Routing to support with sanitized data")
            elif support_response:
                next_agent = "complete"
            else:
                # All workflow stages should be handled above - default to complete
                next_agent = "complete"

            # Track successful supervisor decision
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_decision_success_{next_agent}"
            )

            return {"current_agent": next_agent}

        except Exception as e:

            # Track supervisor error with LDAI metrics
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )

            # Fallback to security agent for safety
            return {"current_agent": "security_agent"}
    def security_node(state: SupervisorState):
        """Route to security agent with LDAI metrics tracking"""
        try:
            
            # Track supervisor orchestration start for security agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_security_start"
            )
            
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
            result = security_agent.invoke(security_input)
            
            # Track successful supervisor orchestration for security agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_security_success"
            )
            
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
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )
            raise
    
    def support_node(state: SupervisorState):
        """Route to support agent with LDAI metrics tracking"""
        try:
            
            # Track supervisor orchestration start for support agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_support_start"
            )
            
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
                support_messages = sanitized_messages + [HumanMessage(content=processed_input)]
            else:
                support_messages = [HumanMessage(content=processed_input)]  # Fallback to redacted current message only

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
                log_student(f"🛡️ PII PROTECTED: {', '.join(pii_types)} redacted")

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
            result = support_agent.invoke(support_input)
            
            # Track successful supervisor orchestration for support agent
            tool_calls = result.get("tool_calls", [])
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_orchestrating_support_success_tools_{len(tool_calls)}"
            )
            
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
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )
            raise
    
    
    def route_decision(state: SupervisorState) -> Literal["pii_prescreen", "security_agent", "support_agent", "complete"]:
        """Route based on supervisor decision with intelligent pre-screening"""
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
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_workflow_complete_tools_{len(support_tool_calls)}"
            )
            
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
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )
            
            # Return error response
            return {
                "final_response": f"I apologize, but I encountered an error finalizing the response: {e}",
                "actual_tool_calls": [],
                "support_tool_details": [],
                "user_input": state["user_input"],
                "workflow_stage": "error"
            }
    
    # Build intelligent supervisor workflow
    workflow = StateGraph(SupervisorState)

    # Add nodes including new PII pre-screening
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("pii_prescreen", pii_prescreen_node)  # New intelligent pre-screening node
    workflow.add_node("security_agent", security_node)
    workflow.add_node("support_agent", support_node)
    workflow.add_node("format_final", format_final)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add intelligent routing with PII pre-screening
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "pii_prescreen": "pii_prescreen",      # New intelligent pre-screening route
            "security_agent": "security_agent",    # Traditional security route
            "support_agent": "support_agent",      # Direct bypass route (new!)
            "complete": "format_final"
        }
    )

    # After PII pre-screening, return to supervisor for routing decision
    workflow.add_edge("pii_prescreen", "supervisor")

    # After each agent, return to supervisor
    workflow.add_edge("security_agent", "supervisor")
    workflow.add_edge("support_agent", "supervisor")
    
    # Final node
    workflow.set_finish_point("format_final")
    
    return workflow.compile()