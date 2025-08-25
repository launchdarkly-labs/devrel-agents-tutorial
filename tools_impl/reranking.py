from langchain.tools import BaseTool
from typing import List

class RerankingTool(BaseTool):
    name: str = "reranking"
    description: str = "Rerank search results based on relevance"
    
    def _run(self, query: str, results: str) -> str:
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
        
        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Return reranked results
        reranked = '\n'.join([result[1] for result in scored_results])
        return f"Reranked results:\n{reranked}"