from typing import TypedDict, List, Annotated, Literal, Optional
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent
from config_manager import AgentConfig, FixedConfigManager as ConfigManager

class SupervisorState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
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

def create_supervisor_agent(supervisor_config: AgentConfig, support_config: AgentConfig, security_config: AgentConfig, config_manager: ConfigManager):
    """Create supervisor agent using LDAI SDK pattern"""
    
    # Create LangChain model directly from config
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    
    model_name = supervisor_config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        supervisor_model = ChatOpenAI(model=supervisor_config.model, temperature=0.0)
    else:
        supervisor_model = ChatAnthropic(model=supervisor_config.model, temperature=0.0)
    
    # Create child agents with config manager
    support_agent = create_support_agent(support_config, config_manager)
    security_agent = create_security_agent(security_config, config_manager)
    
    def supervisor_node(state: SupervisorState):
        """Supervisor decides next step in workflow with LDAI metrics tracking"""
        try:
            messages = state["messages"]
            workflow_stage = state.get("workflow_stage", "initial_security")
            security_cleared = state.get("security_cleared", False)
            support_response = state.get("support_response", "")
            
            print(f"🎯 SUPERVISOR: Stage={workflow_stage}, Security={security_cleared}, Support={bool(support_response)}")
            
            # Track supervisor decision-making process
            decision_start = config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_decision_start"  # Track decision start
            )
            
            # Simplified routing logic
            if workflow_stage == "initial_security" and not security_cleared:
                next_agent = "security_agent"
                print(f"🎯 SUPERVISOR: Rule-based routing -> {next_agent}")
            elif workflow_stage == "research" and not support_response:
                next_agent = "support_agent"
                print(f"🎯 SUPERVISOR: Rule-based routing -> {next_agent}")
            elif support_response:
                next_agent = "complete"
                print(f"🎯 SUPERVISOR: Rule-based routing -> {next_agent}")
            else:
                # Use model for complex routing decisions
                print(f"🎯 SUPERVISOR: Using model for complex routing decision")
                system_prompt = f"""
                {supervisor_config.instructions}
                
                Current stage: {workflow_stage}
                Security cleared: {security_cleared}
                Has support response: {bool(support_response)}
                """
                
                prompt = HumanMessage(content=system_prompt + f"\n\nLast message: {messages[-1].content if messages else state['user_input']}")
                
                # Track model call with LDAI metrics
                response = config_manager.track_metrics(
                    supervisor_config.tracker,
                    lambda: supervisor_model.invoke([prompt])
                )
                
                next_agent = response.content.strip().lower()
                print(f"🎯 SUPERVISOR: Model-based routing -> {next_agent}")
            
            # Track successful supervisor decision
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_decision_success_{next_agent}"
            )
            
            print(f"🎯 SUPERVISOR: Final routing decision -> {next_agent}")
            return {"current_agent": next_agent}
            
        except Exception as e:
            print(f"❌ SUPERVISOR ERROR: {e}")
            
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
            print(f"🎯 SUPERVISOR: Orchestrating security agent execution")
            
            # Track supervisor orchestration start for security agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_security_start"
            )
            
            # Prepare security agent input
            security_input = {
                "user_input": state["user_input"],
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
            
            print(f"🎯 SUPERVISOR: Security agent completed, transitioning {current_stage} -> {new_stage}")
            
            # Extract PII schema fields from security agent
            detected = result.get("detected", False)
            types = result.get("types", [])
            redacted_text = result.get("redacted", state["user_input"])
            
            print(f"🔒 SUPERVISOR: PII detected={detected}, types={types}")
            print(f"🔒 SUPERVISOR DEBUG: Security agent result keys: {list(result.keys())}")
            print(f"🔒 SUPERVISOR DEBUG: Security tool_details: {result.get('tool_details', [])}")
            
            return {
                "messages": [AIMessage(content=result["response"])],
                "workflow_stage": new_stage,
                "security_cleared": True,  # Always proceed after security agent
                "processed_user_input": redacted_text,  # Use redacted text for support agent
                "pii_detected": detected,
                "pii_types": types,
                "redacted_text": redacted_text,
                "security_tool_details": result.get("tool_details", [])  # Capture security agent tool details
            }
            
        except Exception as e:
            print(f"❌ SUPERVISOR: Security agent orchestration error: {e}")
            
            # Track error with LDAI metrics
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
            )
            raise
    
    def support_node(state: SupervisorState):
        """Route to support agent with LDAI metrics tracking"""
        try:
            print(f"🎯 SUPERVISOR: Orchestrating support agent execution")
            
            # Track supervisor orchestration start for support agent
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: "supervisor_orchestrating_support_start"
            )
            
            # Use processed (potentially redacted) text if available
            processed_input = state.get("processed_user_input", state["user_input"])
            pii_detected = state.get("pii_detected", False)
            pii_types = state.get("pii_types", [])
            
            print(f"🔒 SUPERVISOR: Passing to support agent - PII detected: {pii_detected}")
            print(f"📝 SUPERVISOR: Input text: '{processed_input[:100]}...'")
            if pii_types:
                print(f"🔍 SUPERVISOR: PII types found: {pii_types}")
            
            # Prepare support agent input
            support_input = {
                "user_input": processed_input,  # Use redacted text if PII was found
                "response": "",
                "tool_calls": [],
                "tool_details": [],
                "messages": [HumanMessage(content=processed_input)]
            }
            
            # Execute support agent
            result = support_agent.invoke(support_input)
            
            # Track successful supervisor orchestration for support agent
            tool_calls = result.get("tool_calls", [])
            config_manager.track_metrics(
                supervisor_config.tracker,
                lambda: f"supervisor_orchestrating_support_success_tools_{len(tool_calls)}"
            )
            
            print(f"🔧 SUPERVISOR RECEIVED FROM SUPPORT:")
            print(f"   📊 tool_calls: {tool_calls}")
            print(f"   📊 tool_details: {result.get('tool_details', [])}")
            print(f"🎯 SUPERVISOR: Support agent completed with {len(tool_calls)} tools used")
            
            return {
                "messages": [AIMessage(content=result["response"])],
                "support_response": result["response"],
                "support_tool_calls": tool_calls,
                "support_tool_details": result.get("tool_details", []),
                "workflow_stage": "complete"
            }
            
        except Exception as e:
            print(f"❌ SUPERVISOR: Support agent orchestration error: {e}")
            
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
            print(f"🎯 SUPERVISOR: Finalizing workflow")
            
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
            
            print(f"🎯 SUPERVISOR: Workflow completed successfully")
            print(f"   📊 Final response length: {len(final_content)} chars")
            print(f"   📊 Tools used in workflow: {support_tool_calls}")
            
            return {
                "final_response": final_content,
                "actual_tool_calls": support_tool_calls,
                "support_tool_details": state.get("support_tool_details", []),
                "user_input": state["user_input"],
                "workflow_stage": "complete"
            }
            
        except Exception as e:
            print(f"❌ SUPERVISOR: Final formatting error: {e}")
            
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