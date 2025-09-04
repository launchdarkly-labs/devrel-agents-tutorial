from langchain_core.tools import BaseTool
from typing import Dict, Any, List
import re
from .search_v1 import SearchToolV1
from .search_v2 import SearchToolV2
from .pii_detection import PIIDetectionTool

class DynamicTool(BaseTool):
    """A dynamic tool created from LaunchDarkly schema"""
    name: str
    description: str
    
    def __init__(self, tool_name: str, tool_description: str, parameters: Dict[str, Any]):
        self.name = tool_name
        self.description = tool_description
        self.parameters = parameters
        super().__init__()
    
    def _run(self, **kwargs) -> str:
        """Execute the tool based on its name and parameters"""
        
        if self.name == "search_v1":
            return self._execute_search_v1(kwargs.get("query", ""))
        elif self.name == "search_v2":
            # Pass all search parameters from kwargs
            return self._execute_search_v2_with_params(kwargs)
        elif self.name == "reranking":
            return self._execute_reranking(
                kwargs.get("query", ""), 
                kwargs.get("results", "")
            )
        elif self.name == "pii_detection":
            return self._execute_pii_detection(kwargs.get("text", ""))
        else:
            return f"Tool {self.name} not implemented yet"
    
    def _execute_search_v1(self, query: str) -> str:
        """Execute keyword search"""
        tool = SearchToolV1()
        return tool._run(query)
    
    def _execute_search_v2(self, query: str) -> str:
        """Execute vector search with LaunchDarkly parameters"""
        tool = SearchToolV2()
        # Pass LaunchDarkly parameters to the tool
        search_args = {"query": query}
        
        # Add configured parameters from LaunchDarkly
        if self.parameters:
            if "top_k" in self.parameters:
                search_args["top_k"] = self.parameters["top_k"].get("default", 5)
            if "min_score" in self.parameters:
                search_args["min_score"] = self.parameters["min_score"].get("default", 0.2)
        
        return tool._run(**search_args)

    def _execute_search_v2_with_params(self, kwargs: Dict[str, Any]) -> str:
        """Execute vector search with both LaunchDarkly config and runtime parameters"""
        tool = SearchToolV2()
        search_args = {"query": kwargs.get("query", "")}
        
        # Priority: runtime parameters > LaunchDarkly config > tool defaults
        
        # Add LaunchDarkly configured parameters
        if self.parameters:
            if "top_k" in self.parameters:
                search_args["top_k"] = self.parameters["top_k"].get("default", 5)
            if "min_score" in self.parameters:
                search_args["min_score"] = self.parameters["min_score"].get("default", 0.2)
        
        # Override with runtime parameters from LLM tool call
        if "top_k" in kwargs:
            search_args["top_k"] = kwargs["top_k"]
        if "min_score" in kwargs:
            search_args["min_score"] = kwargs["min_score"]
        
        print(f"🔧 SEARCH_V2 PARAMS: LaunchDarkly config + runtime args = {search_args}")
        return tool._run(**search_args)
    
    def _execute_reranking(self, query: str, results: str) -> str:
        """Execute result reranking"""
        lines = results.split('\n')
        
        # Simple scoring based on query term presence
        scored_results = []
        query_lower = query.lower()
        
        for line in lines:
            if line.strip():
                # Count query terms in result
                score = sum(1 for term in query_lower.split() if term in line.lower())
                scored_results.append((score, line))
        
        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Return reranked results
        reranked = '\n'.join([result[1] for result in scored_results])
        return f"Reranked results:\n{reranked}"
    
    def _execute_pii_detection(self, text: str) -> str:
        """Execute PII detection"""
        tool = PIIDetectionTool()
        return tool._run(text)

def create_tools_from_launchdarkly(ai_config: Dict[str, Any]) -> List[BaseTool]:
    """Create tools dynamically from LaunchDarkly AI Config schema"""
    tools = []
    
    # Extract tools from LaunchDarkly structure
    if "model" in ai_config and "parameters" in ai_config["model"] and "tools" in ai_config["model"]["parameters"]:
        tool_definitions = ai_config["model"]["parameters"]["tools"]
        
        for tool_def in tool_definitions:
            name = tool_def.get("name", "unknown")
            description = tool_def.get("description", "No description provided")
            parameters = tool_def.get("parameters", {})
            
            # Create actual tool instances instead of dynamic wrapper
            if name == "search_v1":
                tools.append(SearchToolV1())
            elif name == "search_v2":
                tools.append(SearchToolV2())
            elif name == "pii_detection":
                tools.append(PIIDetectionTool())
            else:
                # Fallback to dynamic tool for unknown tools
                dynamic_tool = DynamicTool(name, description, parameters)
                tools.append(dynamic_tool)
    
    return tools