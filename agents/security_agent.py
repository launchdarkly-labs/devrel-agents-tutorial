from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from policy.config_manager import AgentConfig

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]

def create_security_agent(config: AgentConfig):
    """Create a security agent using native model capabilities for PII detection and compliance"""
    
    # Initialize model - no tools needed, using native capabilities
    model_name = config.model.lower()
    if "gpt" in model_name or "openai" in model_name:
        model = ChatOpenAI(model=config.model, temperature=0.1)
    else:
        model = ChatAnthropic(model=config.model, temperature=0.1)
    
    def should_continue(state: AgentState):
        """Security agent processes directly - no tools needed"""
        return "end"
    
    def call_model(state: AgentState):
        """Call the security model"""
        messages = state["messages"]
        
        # Add system message if first call
        if len(messages) == 1:
            system_prompt = f"""
            {config.instructions}
            
            Use your native capabilities to analyze content directly. No external tools needed.
            """
            messages = [HumanMessage(content=system_prompt)] + messages
        
        response = model.invoke(messages)
        return {"messages": [response]}
    
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
            if isinstance(final_response, list):
                text_parts = []
                for block in final_response:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                final_response = ' '.join(text_parts).strip()
        else:
            final_response = "Security processing completed."
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": [],  # No tools used
            "messages": messages
        }
    
    # Build simplified workflow - no tools needed
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("format", format_final_response)
    
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"end": "format"})
    workflow.set_finish_point("format")
    
    return workflow.compile()