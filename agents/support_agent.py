from dataclasses import dataclass
from typing import TypedDict, List
from langgraph.graph import StateGraph
from typing import Annotated
from langchain_anthropic import ChatAnthropic
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.search import SearchTool
from tools_impl.redaction import RedactionTool
from tools_impl.reranking import RerankingTool
from policy.config_manager import AgentConfig

@dataclass
class ContextSchema:
    variation_key: str
    allowed_tools: List[str]
    policy_limits: dict

class AgentState(TypedDict):
    user_input: str
    response: str
    tool_calls: List[str]

def create_support_agent(config: AgentConfig):
    # Initialize model
    model = ChatAnthropic(
        model=config.model,
        temperature=0.1
    )
    
    # Initialize tools based on configuration
    available_tools = []
    if "search_v1" in config.allowed_tools:
        available_tools.append(SearchToolV1())
    if "search_v2" in config.allowed_tools:
        available_tools.append(SearchToolV2())
    if "search" in config.allowed_tools:
        available_tools.append(SearchTool())
    if "redaction" in config.allowed_tools:
        available_tools.append(RedactionTool())
    if "reranking" in config.allowed_tools:
        available_tools.append(RerankingTool())
    
    def process_query(state: AgentState):        
        # Build prompt with configuration
        prompt = f"""
        {config.instructions}
        
        Available tools: {config.allowed_tools}
        Max tool calls: {config.max_tool_calls}
        
        User question: {state['user_input']}
        """
        
        # Get response from model
        response = model.invoke(prompt)
        
        return {
            "user_input": state["user_input"],
            "response": response.content,
            "tool_calls": []  # Simplified for tutorial
        }
    
    # Create simple workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("process", process_query)
    workflow.set_entry_point("process")
    workflow.set_finish_point("process")
    
    return workflow.compile()