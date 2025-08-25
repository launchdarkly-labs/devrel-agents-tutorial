from langchain.tools import BaseTool
from data.enterprise_kb import get_knowledge_base

class SearchToolV1(BaseTool):
    name: str = "search_v1"
    description: str = "Basic keyword-based search through AI/ML technical documentation"
    
    def _run(self, query: str) -> str:
        docs = get_knowledge_base()
        query_lower = query.lower()
        results = []
        
        for doc in docs:
            if any(term in doc.lower() for term in query_lower.split()):
                results.append(doc)
        
        if not results:
            return "No relevant technical documentation found for your query."
        
        return f"Found {len(results)} relevant documents:\n\n" + "\n\n".join(results[:5])