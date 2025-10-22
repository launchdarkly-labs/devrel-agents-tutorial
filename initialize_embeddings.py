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

    # Auto-detect provider and validate credentials
    auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
    embedding_provider = os.getenv('EMBEDDING_PROVIDER', '').lower()
    has_openai = os.getenv('OPENAI_API_KEY')

    # Determine which provider will be used
    if embedding_provider in ['openai', 'bedrock']:
        provider = embedding_provider
    elif auth_method == 'sso' and not has_openai:
        provider = 'bedrock'
    elif has_openai:
        provider = 'openai'
    else:
        provider = 'openai'  # Default for backward compatibility

    print(f"🔍 Detected embedding provider: {provider}")

    # Validate provider-specific requirements
    if provider == 'openai':
        if not has_openai:
            print(" Error: OPENAI_API_KEY environment variable is required for OpenAI embeddings")
            sys.exit(1)
        print("   Using OpenAI text-embedding-3-small")
    elif provider == 'bedrock':
        if auth_method != 'sso':
            print(" Error: AUTH_METHOD=sso is required for Bedrock embeddings")
            print("   Run: aws sso login")
            sys.exit(1)

        model = os.getenv('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v2:0')
        dimensions = os.getenv('BEDROCK_EMBEDDING_DIMENSIONS', '1024')
        print(f"   Using Bedrock {model} (dimensions: {dimensions})")
        print("   Verifying AWS SSO session...")
    
    try:
        # Initialize vector store
        vector_store = VectorStore()
        
        # Check if embeddings already exist
        if vector_store.exists():
            print("📦 Vector store already exists!")
            print(f"   - Documents: {len(vector_store.documents)}")
            print(f"   - Provider: {vector_store.provider}")
            print(f"   - Model: {vector_store.embedding_model}")
            print(f"   - Dimensions: {vector_store.dimension}")
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
        print(f"   - Provider: {vector_store.provider}")
        print(f"   - Model: {vector_store.embedding_model}")
        print(f"   - Dimensions: {vector_store.dimension}")
        print("   - Embeddings are saved to data/vector_store/")
        print("   - Search tools will now use persistent embeddings")
        
    except Exception as e:
        print(f" Error initializing embeddings: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()