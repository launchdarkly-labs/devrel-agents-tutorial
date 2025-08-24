from langchain.tools import BaseTool
from data.mythical_pets_kb import MYTHICAL_PETS_KB

class SearchToolV1(BaseTool):
    name: str = "search_basic"
    description: str = "Basic keyword-based search through mythical pet care documentation"
    
    def _run(self, query: str) -> str:
        docs = MYTHICAL_PETS_KB
        query_lower = query.lower()
        results = []
        
        for doc in docs:
            if any(term in doc.lower() for term in query_lower.split()):
                results.append(doc)
        
        if not results:
            return "No relevant documentation found for your query."
        
        return f"Found {len(results)} relevant documents:\n\n" + "\n\n".join(results)