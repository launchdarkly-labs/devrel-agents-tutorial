"""
Persistent Vector Database for Knowledge Base
Uses OpenAI embeddings with FAISS for efficient similarity search
"""

import os
import pickle
import numpy as np
from typing import List, Tuple, Optional
from openai import OpenAI
import faiss
from pathlib import Path

class VectorStore:
    def __init__(self, store_path: str = "data/vector_store"):
        self.store_path = Path(store_path)
        self.store_path.mkdir(exist_ok=True)
        
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.embedding_model = "text-embedding-3-small"
        self.dimension = 1536  # text-embedding-3-small dimension
        
        self.index = None
        self.documents = []
        self.metadata = []
        
        # Try to load existing store
        self._load_store()
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for a list of texts using OpenAI"""
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        response = self.client.embeddings.create(
            input=texts,
            model=self.embedding_model
        )
        
        embeddings = np.array([data.embedding for data in response.data])
        return embeddings.astype('float32')
    
    def create_index(self, documents: List[str], metadata: Optional[List[dict]] = None):
        """Create and save vector index from documents"""
        print(f"Creating embeddings for {len(documents)} documents...")
        
        # Get embeddings in batches to avoid API limits
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_embeddings = self._get_embeddings(batch)
            all_embeddings.append(batch_embeddings)
            print(f"Processed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
        
        embeddings = np.vstack(all_embeddings)
        
        # Create FAISS index
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        self.documents = documents
        self.metadata = metadata or [{} for _ in documents]
        
        # Save to disk
        self._save_store()
        print(f"Vector store created and saved with {len(documents)} documents")
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, dict]]:
        """Search for similar documents"""
        if self.index is None:
            raise ValueError("No vector index loaded. Create index first.")
        
        # Get query embedding
        query_embedding = self._get_embeddings([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:  # Valid result
                results.append((
                    self.documents[idx],
                    float(score),
                    self.metadata[idx]
                ))
        
        return results
    
    def _save_store(self):
        """Save vector store to disk"""
        # Save FAISS index
        faiss.write_index(self.index, str(self.store_path / "faiss.index"))
        
        # Save documents and metadata
        with open(self.store_path / "documents.pkl", "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "metadata": self.metadata,
                "dimension": self.dimension,
                "model": self.embedding_model
            }, f)
        
        print(f"Vector store saved to {self.store_path}")
    
    def _load_store(self):
        """Load vector store from disk"""
        index_path = self.store_path / "faiss.index"
        docs_path = self.store_path / "documents.pkl"
        
        if index_path.exists() and docs_path.exists():
            # Load FAISS index
            self.index = faiss.read_index(str(index_path))
            
            # Load documents and metadata
            with open(docs_path, "rb") as f:
                data = pickle.load(f)
                self.documents = data["documents"]
                self.metadata = data["metadata"]
                self.dimension = data.get("dimension", 1536)
                self.embedding_model = data.get("model", "text-embedding-3-small")
            
            print(f"Vector store loaded with {len(self.documents)} documents")
        else:
            print("No existing vector store found")
    
    def exists(self) -> bool:
        """Check if vector store exists"""
        return self.index is not None and len(self.documents) > 0