"""PII sanitization utilities for multi-agent workflows"""

from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from utils.logger import log_debug, log_verbose


def sanitize_messages(original_messages: List[BaseMessage], redacted_text: str) -> List[BaseMessage]:
    """
    Create sanitized message history by replacing PII in human messages with redacted text
    
    Args:
        original_messages: Original message history that may contain PII
        redacted_text: Clean text with PII removed/redacted
        
    Returns:
        List of sanitized messages safe for downstream agents
    """
    sanitized_messages = []
    
    log_debug(f"🔒 PII PROTECTION: Sanitizing {len(original_messages)} messages")
    
    for msg in original_messages:
        if isinstance(msg, HumanMessage):
            # Replace human message content with redacted text
            sanitized_msg = HumanMessage(content=redacted_text)
            sanitized_messages.append(sanitized_msg)
            log_verbose(f"🔒 PII SANITIZED: Original '{msg.content[:50]}...' -> Redacted '{redacted_text[:50]}...'")
        else:
            # Keep other message types as-is
            sanitized_messages.append(msg)
    
    log_verbose(f"🔒 PII PROTECTION: Created {len(sanitized_messages)} sanitized messages for downstream agents")
    return sanitized_messages


def create_redacted_input(user_input: str, processed_input: str, pii_detected: bool, pii_types: List[str]) -> str:
    """
    Create safe input text for downstream agents
    
    Args:
        user_input: Original user input
        processed_input: Processed/redacted input from security agent
        pii_detected: Whether PII was detected
        pii_types: Types of PII found
        
    Returns:
        Safe text to pass to downstream agents
    """
    if pii_detected and pii_types:
        log_debug(f"PII TYPES FOUND: {pii_types}")
        return processed_input
    return user_input


def prepare_safe_agent_input(state: Dict[str, Any], agent_type: str) -> Dict[str, Any]:
    """
    Prepare sanitized input for downstream agents (security or support)
    
    Args:
        state: Current workflow state
        agent_type: Type of agent ("security" or "support")
        
    Returns:
        Safe agent input dictionary
    """
    if agent_type == "security":
        # Security agent gets original input for analysis
        return {
            "user_input": state["user_input"],
            "response": "",
            "tool_calls": [],
            "messages": [HumanMessage(content=state["messages"][-2].content if len(state["messages"]) >= 2 else state["user_input"])]
        }
    
    elif agent_type == "support":
        # Support agent gets sanitized input
        processed_input = state.get("processed_user_input", state["user_input"])
        sanitized_messages = state.get("sanitized_messages", [])
        
        # Use sanitized message history to prevent PII leakage
        if sanitized_messages:
            support_messages = sanitized_messages
            log_debug(f"🔒 SECURITY ENFORCED: Using {len(sanitized_messages)} sanitized messages for support agent")
            # Log what the support agent will actually see
            for i, msg in enumerate(sanitized_messages):
                msg_preview = msg.content[:50] if hasattr(msg, 'content') else str(msg)[:50]
                log_debug(f"🔒 SUPPORT MSG {i}: {type(msg).__name__} - '{msg_preview}...'")
        else:
            # Fallback: create clean message with only redacted text
            support_messages = [HumanMessage(content=processed_input)]
            log_debug(f"FALLBACK: No sanitized messages, using redacted text only")
        
        return {
            "user_input": processed_input,  # Use redacted text if PII was found
            "response": "",
            "tool_calls": [],
            "tool_details": [],
            "messages": support_messages  # CRITICAL: Only sanitized messages passed to support agent
        }
    
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def log_pii_status(state: Dict[str, Any]) -> None:
    """Log PII detection status for debugging"""
    pii_detected = state.get("pii_detected", False)
    pii_types = state.get("pii_types", [])
    processed_input = state.get("processed_user_input", state["user_input"])
    
    log_debug(f"🔒 SUPERVISOR: Passing to support agent - PII detected: {pii_detected}")
    log_debug(f"SUPERVISOR: Input text: '{processed_input[:100]}...'")
    if pii_types:
        log_debug(f"SUPERVISOR: PII types found: {pii_types}")