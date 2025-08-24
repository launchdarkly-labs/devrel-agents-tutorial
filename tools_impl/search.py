from langchain.tools import BaseTool

class SearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for information"
    
    def _run(self, query: str) -> str:
        # Simplified implementation for tutorial
        return f"Search result for: {query}"