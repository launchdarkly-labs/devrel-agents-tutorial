from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
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
    
    # Create LangChain model using official LDAI SDK pattern
    from langchain.chat_models import init_chat_model
    from config_manager import map_provider_to_langchain
    
    # Use provider information from LaunchDarkly config
    if agent_config.provider and hasattr(agent_config.provider, 'name'):
        langchain_provider = map_provider_to_langchain(agent_config.provider.name)
    else:
        # Fallback: infer provider from model name
        model_name = agent_config.model.name.lower()
        if "gpt" in model_name or "openai" in model_name:
            langchain_provider = "openai"
        elif "claude" in model_name or "anthropic" in model_name:
            langchain_provider = "anthropic"
        elif "mistral" in model_name:
            langchain_provider = "mistralai"
        else:
            langchain_provider = "anthropic"  # default
    
    base_model = init_chat_model(
        model=agent_config.model.name,
        model_provider=langchain_provider,
        temperature=0.0
    )

    # Create structured output model for guaranteed PII detection format
    model = base_model.with_structured_output(PIIDetectionResponse)
    
    tracker = agent_config.tracker
    
    
    # NOTE: Instructions are fetched on each call using LaunchDarkly pattern

    def call_model(state: AgentState):
        """Call the security model to get structured PII detection response"""
        try:
            messages = state["messages"]

            # Use LaunchDarkly pattern for security agent
            import asyncio
            from .ld_agent_helpers import create_agent_with_fresh_config, track_langgraph_metrics

            agent, tracker, disabled = asyncio.run(create_agent_with_fresh_config(
                config_manager=config_manager,
                config_key="security-agent",
                user_id=state.get("user_id", "security_user"),
                user_context=state.get("user_context", {}),
                tools=[]  # Security agent doesn't need external tools
            ))

            if disabled:
                # Return safe default if config is disabled
                return {
                    "messages": [AIMessage(content="PII Analysis: detected=false, types=[]")],
                    "detected": False,
                    "types": [],
                    "redacted": state["messages"][0].content if state["messages"] else "",
                    "response": "Security check disabled"
                }

            # Execute security agent with instructions
            pii_response = track_langgraph_metrics(
                tracker,
                lambda: agent.invoke({"messages": messages})
            )

            # Extract the content from the agent's response
            response_content = pii_response["messages"][-1].content if pii_response["messages"] else ""

            # Parse the structured response (basic parsing for now)
            detected = "detected=true" in response_content.lower()
            types = []
            redacted_text = state["messages"][0].content if state["messages"] else ""

            # Simple extraction of types and redacted text from response
            if "types=" in response_content:
                try:
                    types_part = response_content.split("types=")[1].split(",")[0].strip()
                    if types_part and types_part != "[]":
                        types = [t.strip().strip("[]'\"") for t in types_part.split(",") if t.strip()]
                except:
                    pass

            if "redacted=" in response_content:
                try:
                    redacted_text = response_content.split("redacted=")[1].strip().strip("'\"")
                except:
                    pass


            # Store structured results in state and create AI message for conversation flow
            response_message = AIMessage(content=f"PII Analysis: detected={detected}, types={types}")

            return {
                "messages": [response_message],
                "detected": detected,
                "types": types,
                "redacted": redacted_text,
                "response": response_content
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