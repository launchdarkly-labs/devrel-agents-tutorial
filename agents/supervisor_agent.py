from typing import TypedDict, List, Annotated, Literal, Optional
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent
from config_manager import FixedConfigManager as ConfigManager
from utils.logger import log_student

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
    
    # Create LangChain model using official LDAI SDK pattern
    from langchain.chat_models import init_chat_model
    from config_manager import map_provider_to_langchain
    
    # Use provider information from LaunchDarkly config
    if supervisor_config.provider and hasattr(supervisor_config.provider, 'name'):
        langchain_provider = map_provider_to_langchain(supervisor_config.provider.name)
    else:
        # Fallback: infer provider from model name
        model_name = supervisor_config.model.name.lower()
        if "gpt" in model_name or "openai" in model_name:
            langchain_provider = "openai"
        elif "claude" in model_name or "anthropic" in model_name:
            langchain_provider = "anthropic"
        else:
            langchain_provider = "anthropic"  # default
    
    supervisor_model = init_chat_model(
        model=supervisor_config.model.name,
        model_provider=langchain_provider,
        temperature=0.0
    )
    
    # Create child agents with config manager
    support_agent = create_support_agent(support_config, config_manager)
    security_agent = create_security_agent(security_config, config_manager)
    
    log_student(f"🎯 SUPERVISOR INSTRUCTIONS: {supervisor_config.instructions}")
    
    def supervisor_node(state: SupervisorState):
        """Supervisor decides next step in workflow with LDAI metrics tracking"""
        try:
            messages = state["messages"]
            workflow_stage = state.get("workflow_stage", "initial_security")
            security_cleared = state.get("security_cleared", False)
            support_response = state.get("support_response", "")
            
            # Track supervisor decision-making process
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_decision_start"
            )
            
            # Simplified routing logic
            if workflow_stage == "initial_security" and not security_cleared:
                next_agent = "security_agent"
            elif workflow_stage == "research" and not support_response:
                next_agent = "support_agent"
                log_student(f"🎯 ROUTING: Proceeding to support agent")
            elif support_response:
                next_agent = "complete"
            else:
                # Use model for complex routing decisions
                import asyncio
                from .ld_agent_helpers import create_agent_with_fresh_config

                agent, tracker, disabled = asyncio.run(create_agent_with_fresh_config(
                    config_manager=config_manager,
                    config_key="supervisor-agent",
                    user_id=state.get("user_id", "supervisor_user"),
                    user_context=state.get("user_context", {}),
                    tools=[]  # Supervisor doesn't need tools for routing
                ))

                if disabled:
                    next_agent = "complete"
                else:
                    from langchain_core.messages import HumanMessage
                    routing_message = HumanMessage(content=f"Current stage: {workflow_stage}, Security cleared: {security_cleared}, Has support response: {bool(support_response)}\n\nLast message: {messages[-1].content if messages else state['user_input']}")

                    from .ld_agent_helpers import track_langgraph_metrics
                    response = track_langgraph_metrics(
                        tracker,
                        lambda: agent.invoke({"messages": [routing_message]})
                    )
                    next_agent = response["messages"][-1].content.strip().lower()
            
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
            
            # Fallback to security agent
            return {"current_agent": "security_agent"}
    
    def security_node(state: SupervisorState):
        """Route to security agent with LDAI metrics tracking"""
        try:
            log_student(f"🔐 SECURITY INSTRUCTIONS: {security_config.instructions}")
            
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
            
            # Update workflow stage
            current_stage = state.get("workflow_stage", "initial_security")
            new_stage = "research" if current_stage == "initial_security" else "complete"
            
            
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
            log_student(f"🔧 SUPPORT INSTRUCTIONS: {support_config.instructions}")
            
            # Track supervisor orchestration start for support agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_support_start"
            )
            
            # Use processed (potentially redacted) text if available
            processed_input = state.get("processed_user_input", state["user_input"])
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
            
            # ===== SUPPORT AGENT COMPLETE PII ISOLATION =====
            # This input contains ONLY sanitized/redacted content
            # Support agent operates in completely PII-free environment

            # Log security verification: confirm only sanitized content is passed
            log_student(f"🔒 SECURITY VERIFIED: Support agent receiving {len(support_messages)} sanitized messages")
            if pii_detected:
                log_student(f"🛡️ PII ISOLATION: Original content with {', '.join(pii_types)} has been redacted")

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
            
            # Show support agent response to students
            support_response = result["response"]
            log_student(f"🔧 SUPPORT RESPONSE: {support_response[:200]}{'...' if len(support_response) > 200 else ''}")
            
            tool_details = result.get('tool_details', [])

            return {
                "messages": [AIMessage(content=result["response"])],
                "support_response": result["response"],
                "support_tool_calls": tool_calls,
                "support_tool_details": result.get("tool_details", []),
                "workflow_stage": "complete"
            }
            
        except Exception as e:
            
            # Track error with LDAI metrics
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )
            raise
    
    def revise_node(state: SupervisorState):
        """Ask support agent to revise for clarity"""
        revision_prompt = f"""
        Please revise the following response for better clarity and readability:
        
        {state.get("support_response", "No response to revise")}
        
        Make it more clear, well-structured, and easy to understand.
        """
        
        support_input = {
            "user_input": revision_prompt,
            "response": "",
            "tool_calls": [],
            "messages": [HumanMessage(content=revision_prompt)]
        }
        
        result = support_agent.invoke(support_input)
        
        return {
            "messages": [AIMessage(content=result["response"])],
            "support_response": result["response"],
            "workflow_stage": "final_compliance"
        }
    
    def route_decision(state: SupervisorState) -> Literal["security_agent", "support_agent", "revise", "complete"]:
        """Route based on supervisor decision"""
        current_agent = state.get("current_agent", "security_agent")
        
        if "security" in current_agent:
            return "security_agent"
        elif "support" in current_agent:
            return "support_agent"
        elif "revise" in current_agent:
            return "revise"
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
    
    # Build supervisor workflow
    workflow = StateGraph(SupervisorState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("security_agent", security_node)
    workflow.add_node("support_agent", support_node)
    workflow.add_node("revise", revise_node)
    workflow.add_node("format_final", format_final)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add routing
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "security_agent": "security_agent",
            "support_agent": "support_agent", 
            "revise": "revise",
            "complete": "format_final"
        }
    )
    
    # After each agent, return to supervisor
    workflow.add_edge("security_agent", "supervisor")
    workflow.add_edge("support_agent", "supervisor")
    workflow.add_edge("revise", "supervisor")
    
    # Final node
    workflow.set_finish_point("format_final")
    
    return workflow.compile()