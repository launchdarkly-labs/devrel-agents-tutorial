#!/usr/bin/env python3
"""
Test RAG Search (developer debugging utility, not part of the tutorial flow).

Verifies that the knowledge base is properly indexed and searchable. Run this
when you suspect the vector store is stale or returning bad chunks.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from data.vector_store import VectorStore


def test_rag(query: str, top_k: int = 3):
    """Test RAG search with a query"""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    try:
        vector_store = VectorStore()

        if not vector_store.exists():
            print("\nVector store not found. Run initialize_embeddings.py first:")
            print("  uv run python initialize_embeddings.py")
            sys.exit(1)

        results = vector_store.search(query, top_k=top_k)

        if not results:
            print("\nNo results found.")
            return

        print(f"\nTop {len(results)} results:\n")

        for i, (doc, score, metadata) in enumerate(results, 1):
            print(f"--- Result {i} (score: {score:.3f}) ---")
            # Truncate long documents for display
            display_text = doc[:500] + "..." if len(doc) > 500 else doc
            print(display_text)
            print()

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python tools/test_rag.py <query>")
        print("\nExamples:")
        print('  uv run python tools/test_rag.py "What is the refund policy?"')
        print('  uv run python tools/test_rag.py "function timeout limit"')
        print('  uv run python tools/test_rag.py "GDPR compliance"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    test_rag(query)


if __name__ == "__main__":
    main()
