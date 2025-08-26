from langchain.tools import BaseTool
from typing import List

class RerankingTool(BaseTool):
    name: str = "reranking"
    description: str = "Rerank and organize search results by relevance to the original query. Use this when you have search results that need to be ordered by importance or relevance."
    
    def _run(self, query: str, results: str) -> str:
        print(f"DEBUG: RerankingTool called with query='{query[:50]}...', results='{results[:100]}...'")
        
        # Validate inputs
        if not query or not results:
            return "Error: Reranking requires both query and results parameters."
        
        # Simulate reranking logic
        lines = results.split('\n')
        
        # Simple scoring based on query term presence
        scored_results = []
        query_lower = query.lower()
        
        for line in lines:
            if line.strip():
                # Count query terms in result
                score = sum(1 for term in query_lower.split() if term in line.lower())
                scored_results.append((score, line))
        
        if not scored_results:
            return "No results to rerank."
        
        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Return reranked results
        reranked = '\n'.join([result[1] for result in scored_results])
        result = f"Reranked results by relevance to '{query}':\n{reranked}"
        print(f"DEBUG: RerankingTool returning: {result[:100]}...")
        return result