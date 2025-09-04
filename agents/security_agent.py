from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from config_manager import AgentConfig, FixedConfigManager as ConfigManager

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

def create_security_agent(agent_config: AgentConfig, config_manager: ConfigManager):
    """Create security agent with PII detection tools"""
    
    # Clear cache to ensure latest config
    config_manager.clear_cache()
    
    # Create LangChain model from LDAI agent configuration
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    
    # Use provider.name from config instead of parsing model name
    provider_name = getattr(agent_config, 'provider', {}).get('name', '').lower()
    if provider_name == 'openai':
        model = ChatOpenAI(model=agent_config.model, temperature=0.0)
    elif provider_name == 'anthropic':
        model = ChatAnthropic(model=agent_config.model, temperature=0.0)
    else:
        # Fallback to Anthropic if provider not specified or unknown
        model = ChatAnthropic(model=agent_config.model, temperature=0.0)
    
    tracker = agent_config.tracker
    
    # Security agent doesn't use tools - it provides direct JSON responses
    tools = []
    
    print(f"🔐 CREATING SECURITY AGENT: Using LDAI model {agent_config.model} (no tools - direct JSON responses)")
    print(f"🔐 SECURITY INSTRUCTIONS: {agent_config.instructions[:200]}...")
    
    # Store config values for nested functions
    config_instructions = agent_config.instructions
    
    def call_model(state: AgentState):
        """Call the security model to get direct JSON response"""
        try:
            messages = state["messages"]
            
            # Add system message with instructions if this is the first call
            if len(messages) == 1:  # Only user message
                system_prompt = config_instructions
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Track model call with LDAI metrics
            response = config_manager.track_metrics(
                tracker,
                lambda: model.invoke(messages)
            )
            
            print(f"🔐 SECURITY MODEL RESPONSE: {len(response.content) if response.content else 0} chars")
            
            return {"messages": [response]}
            
        except Exception as e:
            print(f"❌ SECURITY ERROR: {e}")
            
            # Track error with LDAI metrics
            try:
                config_manager.track_metrics(
                    tracker,
                    lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
                )
            except:
                pass
            
            error_response = AIMessage(content="Security processing encountered an error.")
            return {"messages": [error_response]}
    
    def parse_json_response(state: AgentState):
        """Parse JSON from the security model response"""
        try:
            messages = state["messages"]
            last_message = messages[-1]
            
            # Get the response content
            response_content = last_message.content
            if isinstance(response_content, list):
                # Handle content blocks format
                text_content = ""
                for block in response_content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_content += block.get('text', '')
                response_content = text_content
            
            print(f"🔍 SECURITY PARSING RESPONSE: {response_content[:200]}...")
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON object in the response
            json_match = re.search(r'\{[^{}]*"detected"[^{}]*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                pii_results = json.loads(json_str)
                print(f"🔍 PARSED JSON: {pii_results}")
            else:
                # Fallback - no JSON found
                print("⚠️ No JSON found in response, using defaults")
                pii_results = {
                    "detected": False,
                    "types": [],
                    "redacted": state.get("user_input", "")
                }
            
            return {
                "detected": pii_results.get("detected", False),
                "types": pii_results.get("types", []),
                "redacted": pii_results.get("redacted", state.get("user_input", "")),
                "tool_calls": [],
                "tool_details": []
            }
            
        except Exception as e:
            print(f"❌ JSON PARSING ERROR: {e}")
            # Return safe defaults
            return {
                "detected": False,
                "types": [],
                "redacted": state.get("user_input", ""),
                "tool_calls": [],
                "tool_details": []
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
            if isinstance(final_response, list):
                text_parts = []
                for block in final_response:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                final_response = ' '.join(text_parts).strip()
        else:
            final_response = "Security processing completed."
        
        # Get PII results from state (set by parse_json_response)
        pii_detected = state.get("detected", False)
        pii_types = state.get("types", [])
        redacted_text = state.get("redacted", state.get("user_input", ""))
        
        print(f"🔍 PII RESULTS: detected={pii_detected}, types={pii_types}")
        print(f"🔒 SECURITY CLEARANCE: USE_REDACTED_TEXT - Text: '{redacted_text[:50]}...'")
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": state.get("tool_calls", []),
            "tool_details": state.get("tool_details", []),
            "messages": messages,
            # Return the exact PII schema fields for supervisor and UI
            "detected": pii_detected,
            "types": pii_types, 
            "redacted": redacted_text
        }
    
    # Build simple workflow: call model -> parse JSON -> format response
    workflow = StateGraph(AgentState)
    workflow.add_node("call_model", call_model)
    workflow.add_node("parse_json", parse_json_response)
    workflow.add_node("format", format_final_response)
    
    workflow.set_entry_point("call_model")
    workflow.add_edge("call_model", "parse_json")
    workflow.add_edge("parse_json", "format")
    workflow.set_finish_point("format")
    
    return workflow.compile()