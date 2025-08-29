from langchain.tools import BaseTool
from data.vector_store import VectorStore
from typing import Any

class SearchToolV2(BaseTool):
    name: str = "search_v2"
    description: str = "Advanced vector-based semantic search through enterprise AI/ML documentation using OpenAI embeddings"
    vector_store: Any = None
    
    def __init__(self):
        super().__init__()
        object.__setattr__(self, 'vector_store', VectorStore())
        
        if not self.vector_store.exists():
            raise ValueError("Vector embeddings not initialized. Run 'uv run initialize_embeddings.py' first.")
    
    def _run(self, query: str) -> str:
        try:
            # Search using persistent vector embeddings
            results = self.vector_store.search(query, top_k=3)
            
            if not results:
                return "No relevant documentation found for your query."
            
            # Filter results with minimum similarity threshold (lowered for broader matching)
            relevant_results = [(doc, score, meta) for doc, score, meta in results if score > 0.2]
            
            if not relevant_results:
                return "No relevant documentation found for your query in the knowledge base."
            
            result = f"Found {len(relevant_results)} relevant documents:\n\n"
            for i, (doc, score, metadata) in enumerate(relevant_results):
                result += f"[Relevance: {score:.3f}] {doc}\n\n"
            
            return result
            
        except Exception as e:
            return f"Search error: {str(e)}. Ensure vector embeddings are initialized with 'uv run initialize_embeddings.py'"