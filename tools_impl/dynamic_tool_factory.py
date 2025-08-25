from langchain.tools import BaseTool
from typing import Dict, Any, List
import re
from data.mythical_pets_kb import MYTHICAL_PETS_KB
from .search_v1 import SearchToolV1
from .search_v2 import SearchToolV2

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
            return self._execute_search_v2(kwargs.get("query", ""))
        elif self.name == "redaction":
            return self._execute_redaction(kwargs.get("text", ""))
        elif self.name == "reranking":
            return self._execute_reranking(
                kwargs.get("query", ""), 
                kwargs.get("results", "")
            )
        else:
            return f"Tool {self.name} not implemented yet"
    
    def _execute_search_v1(self, query: str) -> str:
        """Execute keyword search"""
        tool = SearchToolV1()
        return tool._run(query)
    
    def _execute_search_v2(self, query: str) -> str:
        """Execute vector search"""
        tool = SearchToolV2()
        return tool._run(query)
    
    def _execute_redaction(self, text: str) -> str:
        """Execute PII redaction"""
        redacted = text
        
        # Redact email addresses
        redacted = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', redacted)
        
        # Redact phone numbers
        redacted = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', redacted)
        
        # Redact SSN patterns
        redacted = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]', redacted)
        
        return f"Redacted text: {redacted}"
    
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
            
            # Create dynamic tool instance
            dynamic_tool = DynamicTool(name, description, parameters)
            tools.append(dynamic_tool)
    
    return tools