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
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    user_id: str  # For LaunchDarkly targeting
    user_context: dict  # For LaunchDarkly targeting
    response: str
    tool_calls: List[str]
    tool_details: List[dict]
    # PII detection schema fields
    detected: bool
    types: List[str]
    redacted: str

def create_security_agent(agent_config, config_manager: ConfigManager):
    """Create security agent with PII detection tools"""
    
    # Clear cache to ensure latest config
    config_manager.clear_cache()
    
    # NOTE: Model will be created at runtime with fresh LaunchDarkly config
    
    
    # NOTE: Instructions are fetched on each call using LaunchDarkly pattern

    def call_model(state: AgentState):
        """Call the security model to get structured PII detection response"""
        try:
            messages = state["messages"]

            # Fetch config dynamically for each call
            import asyncio

            # Get latest config from LaunchDarkly
            user_context = state.get("user_context", {})
            user_id = state.get("user_id", "security_user")

            agent_config = asyncio.run(config_manager.get_config(
                user_id=user_id,
                config_key="security-agent",
                user_context=user_context
            ))

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
            structured_model = base_model.with_structured_output(PIIDetectionResponse)

            # Create system message with current instructions from LaunchDarkly
            system_message = SystemMessage(content=agent_config.instructions)
            full_messages = [system_message] + messages

            # Call model with structured output
            pii_result = structured_model.invoke(full_messages)

            # Track metrics
            config_manager.track_metrics(
                agent_config.tracker,
                lambda: "security_pii_detection_success"
            )

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
                config_manager.track_metrics(
                    tracker,
                    lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
                )
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
            log_student(f"🔒 PII PROTECTION: {pii_summary} → Text sanitized for downstream agents")
            log_student(f"🔒 REDACTED TEXT: '{redacted_text[:50]}...' (truncated for display)")
        else:
            log_student(f"🔒 PII PROTECTION: No sensitive data detected → Original text preserved")
        
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
    
    # Build simple workflow: call model -> format response (no JSON parsing needed)
    workflow = StateGraph(AgentState)
    workflow.add_node("call_model", call_model)
    workflow.add_node("format", format_final_response)
    
    workflow.set_entry_point("call_model")
    workflow.add_edge("call_model", "format")
    workflow.set_finish_point("format")
    
    return workflow.compile()