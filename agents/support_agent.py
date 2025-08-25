from .model_driven_agent import create_model_driven_agent
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
    # Initialize the workflow engine with LaunchDarkly configuration
    workflow_engine = WorkflowEngine(config)
    
    async def process_query(state: AgentState):
        # Execute multi-step workflow
        result = await workflow_engine.execute_workflow(state['user_input'])
        
        return {
            "user_input": state["user_input"],
            "response": result["response"],
            "tool_calls": result["tool_calls"]
        }
    
    # Create simple workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("process", process_query)
    workflow.set_entry_point("process")
    workflow.set_finish_point("process")
    
    return workflow.compile()