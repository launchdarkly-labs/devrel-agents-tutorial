from dataclasses import dataclass
from typing import TypedDict, List
from langgraph.graph import StateGraph
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.redaction import RedactionTool
from tools_impl.reranking import RerankingTool
from policy.config_manager import AgentConfig

class AgentState(TypedDict):
    user_input: str
    response: str
    tool_calls: List[str]

def create_model_driven_agent(config: AgentConfig):
    """Create an agent where the MODEL decides which tools to use"""
    
    # Create tools based on LaunchDarkly configuration
    available_tools = []
    for tool_name in config.allowed_tools:
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
        elif tool_name == "redaction":
            available_tools.append(RedactionTool())
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
    
    # Initialize model based on LaunchDarkly config
    if "gpt" in config.model.lower() or "openai" in config.model.lower():
        model = ChatOpenAI(
            model=config.model,
            temperature=0.1
        )
    else:
        model = ChatAnthropic(
            model=config.model,
            temperature=0.1
        )
    
    # Bind tools to model so it can decide when to use them
    if available_tools:
        model = model.bind_tools(available_tools)
    
    def process_query(state: AgentState):
        """Let the model decide which tools to use"""
        
        # Create a simple prompt that lets the model decide
        prompt = f"""
        {config.instructions}
        
        Available tools: {[tool.name for tool in available_tools]}
        
        User question: {state['user_input']}
        
        Decide which tools (if any) would be helpful to answer this question accurately.
        """
        
        # Get response from model (model decides tool usage)
        response = model.invoke(prompt)
        
        # Handle tool calls if the model chose to use tools
        tool_calls = []
        final_response = response.content
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = [call['name'] for call in response.tool_calls]
            
            # Execute the tools the model chose
            tool_results = []
            for tool_call in response.tool_calls:
                for tool in available_tools:
                    if tool.name == tool_call['name']:
                        try:
                            result = tool._run(**tool_call['args'])
                            tool_results.append(f"{tool.name}: {result}")
                        except Exception as e:
                            tool_results.append(f"{tool.name}: Error - {str(e)}")
                        break
            
            # If tools were used, generate final response with results
            if tool_results:
                final_prompt = f"""
                {config.instructions}
                
                User question: {state['user_input']}
                
                Tool results:
                {chr(10).join(tool_results)}
                
                Based on the tool results above, provide a comprehensive answer to the user's question.
                """
                
                final_response_obj = model.invoke(final_prompt)
                final_response = final_response_obj.content
        
        # Handle different response content types
        if isinstance(final_response, list):
            final_response = ' '.join([
                block.get('text', '') for block in final_response 
                if block.get('type') == 'text'
            ])
        
        return {
            "user_input": state["user_input"],
            "response": final_response,
            "tool_calls": tool_calls
        }
    
    # Create simple workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("process", process_query)
    workflow.set_entry_point("process")
    workflow.set_finish_point("process")
    
    return workflow.compile()