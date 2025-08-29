from typing import TypedDict, List, Annotated, Literal, Optional
from langgraph.graph import StateGraph, add_messages
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from .support_agent import create_support_agent
from .security_agent import create_security_agent
from policy.config_manager import AgentConfig

class SupervisorState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    current_agent: str
    security_cleared: bool
    support_response: str
    support_tool_calls: List[str]
    support_tool_details: List[dict]
    final_response: str
    workflow_stage: str  # "initial_security", "research", "revision", "final_compliance"

def create_supervisor_agent(supervisor_config: AgentConfig, support_config: AgentConfig, security_config: AgentConfig, metrics_tracker: Optional['AIMetricsTracker'] = None):
    """Create supervisor agent that orchestrates the workflow"""
    
    # Initialize supervisor model
    model_name = supervisor_config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        supervisor_model = ChatOpenAI(model=supervisor_config.model, temperature=supervisor_config.temperature)
    else:
        supervisor_model = ChatAnthropic(model=supervisor_config.model, temperature=supervisor_config.temperature)
    
    # Create child agents
    support_agent = create_support_agent(support_config)
    security_agent = create_security_agent(security_config)
    
    def supervisor_node(state: SupervisorState):
        """Supervisor decides next step in workflow"""
        messages = state["messages"]
        workflow_stage = state.get("workflow_stage", "initial_security")
        security_cleared = state.get("security_cleared", False)
        support_response = state.get("support_response", "")
        
        print(f"DEBUG: Supervisor decision - Stage: {workflow_stage}, Security cleared: {security_cleared}, Has support response: {bool(support_response)}")
        
        # Simplified logic based on workflow stage
        if workflow_stage == "initial_security" and not security_cleared:
            next_agent = "security_agent"
        elif workflow_stage == "research" and not support_response:
            next_agent = "support_agent"
        elif workflow_stage == "final_compliance" and support_response:
            next_agent = "security_agent"  # Final compliance check
        elif support_response and security_cleared:
            next_agent = "complete"
        else:
            # Fallback to model decision
            system_prompt = f"""
            {supervisor_config.instructions}
            
            Current stage: {workflow_stage}
            Security cleared: {security_cleared}
            Has support response: {bool(support_response)}
            
            Choose next action:
            - "security_agent": For PII removal or compliance
            - "support_agent": For research and information
            - "complete": When workflow is finished
            
            Respond with ONLY the agent name.
            """
            
            prompt = HumanMessage(content=system_prompt + f"\n\nLast message: {messages[-1].content if messages else state['user_input']}")
            response = supervisor_model.invoke([prompt])
            next_agent = response.content.strip().lower()
        
        print(f"DEBUG: Supervisor routing to: {next_agent}")
        
        return {"current_agent": next_agent}
    
    def security_node(state: SupervisorState):
        """Route to security agent"""
        # Track security agent start
        agent_start = None
        if metrics_tracker:
            agent_start = metrics_tracker.track_agent_start("security-agent", security_config.model, security_config.variation_key)
        
        try:
            # Prepare input for security agent
            security_input = {
                "user_input": state["user_input"],
                "response": "",
                "tool_calls": [],
                "messages": [HumanMessage(content=state["messages"][-2].content if len(state["messages"]) >= 2 else state["user_input"])]
            }
            
            result = security_agent.invoke(security_input)
            
            # Track security agent completion
            if metrics_tracker and agent_start:
                metrics_tracker.track_agent_completion(
                    "security-agent", security_config.model, security_config.variation_key,
                    agent_start, [], True  # Security agent doesn't use tools
                )
                
        except Exception as e:
            # Track security agent failure
            if metrics_tracker and agent_start:
                metrics_tracker.track_agent_completion(
                    "security-agent", security_config.model, security_config.variation_key,
                    agent_start, [], False, str(e)
                )
            raise
        
        # Update workflow stage
        current_stage = state.get("workflow_stage", "initial_security")
        if current_stage == "initial_security":
            new_stage = "research"
        else:
            new_stage = "complete"
        
        return {
            "messages": [AIMessage(content=result["response"])],
            "workflow_stage": new_stage,
            "security_cleared": True
        }
    
    def support_node(state: SupervisorState):
        """Route to support agent"""
        # Track support agent start
        agent_start = None
        if metrics_tracker:
            agent_start = metrics_tracker.track_agent_start("support-agent", support_config.model, support_config.variation_key)
        
        try:
            # Prepare input for support agent
            support_input = {
                "user_input": state["user_input"],
                "response": "",
                "tool_calls": [],
                "tool_details": [],
                "messages": [HumanMessage(content=state["user_input"])]
            }
            
            result = support_agent.invoke(support_input)
            
            print(f"🔧 SUPERVISOR RECEIVED FROM SUPPORT:")
            print(f"   📊 tool_calls: {result.get('tool_calls', [])}")
            print(f"   📊 tool_details: {result.get('tool_details', [])}")
            
            # Track support agent completion
            if metrics_tracker and agent_start:
                tool_calls = result.get("tool_calls", [])
                metrics_tracker.track_agent_completion(
                    "support-agent", support_config.model, support_config.variation_key,
                    agent_start, tool_calls, True
                )
                
        except Exception as e:
            # Track support agent failure
            if metrics_tracker and agent_start:
                metrics_tracker.track_agent_completion(
                    "support-agent", support_config.model, support_config.variation_key,
                    agent_start, [], False, str(e)
                )
            raise
        
        return {
            "messages": [AIMessage(content=result["response"])],
            "support_response": result["response"],
            "support_tool_calls": result.get("tool_calls", []),
            "support_tool_details": result.get("tool_details", []),
            "workflow_stage": "final_compliance"
        }
    
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
        """Format final response"""
        # Use the support response as the main response, since it contains the helpful answer
        support_response = state.get("support_response", "")
        support_tool_calls = state.get("support_tool_calls", [])
        
        # If we have a support response, use it; otherwise fall back to last message
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