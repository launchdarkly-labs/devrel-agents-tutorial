#!/usr/bin/env python3
"""
Initialize Vector Embeddings
Run this script once to create persistent vector embeddings from your knowledge base
"""

import os
import sys
from dotenv import load_dotenv
from data.vector_store import VectorStore
from data.enterprise_kb import get_knowledge_base

# Load environment variables from .env file
load_dotenv()

def main():
    print(" Initializing vector embeddings for knowledge base...")
    
    # Check required environment variables
    if not os.getenv('OPENAI_API_KEY'):
        print(" Error: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    try:
        # Initialize vector store
        vector_store = VectorStore()
        
        # Check if embeddings already exist
        if vector_store.exists():
            print("📦 Vector store already exists!")
            print(f"   - Documents: {len(vector_store.documents)}")
            print("   - Use --force to recreate embeddings")
            
            if "--force" not in sys.argv:
                return
            else:
                print("🔄 Force recreating embeddings...")
        
        # Load knowledge base
        print(" Loading knowledge base...")
        documents = get_knowledge_base()
        print(f"   - Loaded {len(documents)} documents")
        
        # Create metadata for each document
        metadata = [{"source": "enterprise_kb", "doc_id": i} for i in range(len(documents))]
        
        # Create embeddings
        print(" Creating vector embeddings...")
        vector_store.create_index(documents, metadata)
        
        # Test the embeddings
        print("🧪 Testing search functionality...")
        test_results = vector_store.search("reinforcement learning", top_k=3)
        
        print(" Test results:")
        for i, (doc, score, meta) in enumerate(test_results):
            print(f"   {i+1}. Score: {score:.3f} - {doc[:100]}...")
        
        print("🎉 Vector embeddings initialized successfully!")
        print("   - Embeddings are saved to data/vector_store/")
        print("   - Search tools will now use persistent embeddings")
        
    except Exception as e:
        print(f" Error initializing embeddings: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()