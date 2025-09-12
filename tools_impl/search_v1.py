from langchain.tools import BaseTool
from data.vector_store import VectorStore
from typing import Any

class SearchToolV1(BaseTool):
    name: str = "search_v1"
    description: str = "Basic keyword-based search through enterprise documentation"
    vector_store: Any = None
    
    def __init__(self):
        super().__init__()
        object.__setattr__(self, 'vector_store', VectorStore())
        
        if not self.vector_store.exists():
            raise ValueError("Vector embeddings not initialized. Run 'uv run initialize_embeddings.py' first.")
    
    def _run(self, query: str) -> str:
        try:
            # Get all chunks from persistent store and do keyword search
            if not self.vector_store.documents:
                return "No documentation available."
            
            query_lower = query.lower()
            matching_chunks = []
            
            # Keyword-based search through individual text chunks
            for i, chunk in enumerate(self.vector_store.documents):
                if any(term in chunk.lower() for term in query_lower.split()):
                    matching_chunks.append((i, chunk))
            
            if not matching_chunks:
                return "No relevant text chunks found for your query."
            
            # Format results showing chunk matches
            result = f"Found {len(matching_chunks)} matching text chunks:\n\n"
            for i, (chunk_id, chunk_text) in enumerate(matching_chunks[:5]):
                # Truncate very long chunks for readability
                display_text = chunk_text[:500] + "..." if len(chunk_text) > 500 else chunk_text
                result += f"[Chunk {chunk_id}] {display_text}\n\n"
            
            if len(matching_chunks) > 5:
                result += f"... and {len(matching_chunks) - 5} more chunks"
            
            return result
            
        except Exception as e:
            return f"Search error: {str(e)}. Ensure vector embeddings are initialized with 'uv run initialize_embeddings.py'"