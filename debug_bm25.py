#!/usr/bin/env python3
"""
Debug BM25 scoring issue
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from tools_impl.reranking import RerankingTool
from rank_bm25 import BM25Okapi

def debug_bm25():
    """Debug the BM25 scoring issue"""

    reranking_tool = RerankingTool()

    # Test data
    query = "machine learning algorithms"
    docs = [
        "Deep learning is a subset of machine learning with neural networks",
        "Random forest is a popular machine learning algorithm for classification",
        "Linear regression is a simple statistical method",
        "Support vector machines are effective for classification tasks"
    ]

    print(f"Query: '{query}'")
    print(f"Documents: {docs}")

    # Test tokenization
    query_tokens = reranking_tool._tokenize(query)
    print(f"\nQuery tokens: {query_tokens}")

    tokenized_docs = [reranking_tool._tokenize(doc) for doc in docs]
    print(f"Tokenized docs: {tokenized_docs}")

    # Test BM25 directly
    print(f"\nCreating BM25 with tokenized_docs: {tokenized_docs}")
    print(f"All docs non-empty: {all(len(doc) > 0 for doc in tokenized_docs)}")

    bm25 = BM25Okapi(tokenized_docs)
    scores = bm25.get_scores(query_tokens)
    print(f"BM25 scores: {scores}")

    # Debug BM25 internals
    print(f"BM25 corpus size: {bm25.corpus_size}")
    print(f"BM25 doc lengths: {bm25.doc_len}")
    print(f"BM25 avgdl: {bm25.avgdl}")
    print(f"BM25 doc_freqs type: {type(bm25.doc_freqs)}")

    # Handle different versions of rank_bm25
    if hasattr(bm25, 'doc_freqs') and isinstance(bm25.doc_freqs, dict):
        print(f"BM25 doc freqs keys (first 10): {list(bm25.doc_freqs.keys())[:10]}")
        for token in query_tokens:
            freq = bm25.doc_freqs.get(token, 0)
            print(f"Token '{token}' appears in {freq} documents")
    else:
        print("BM25 doc_freqs not accessible or not a dict")

    # Check BM25 internal attributes
    print(f"BM25 attributes: {[attr for attr in dir(bm25) if not attr.startswith('_')]}")

    # Check IDF values
    print(f"\nBM25 IDF values:")
    if hasattr(bm25, 'idf') and isinstance(bm25.idf, dict):
        for token in query_tokens:
            idf_val = bm25.idf.get(token, 'NOT_FOUND')
            print(f"  '{token}': {idf_val}")
        print(f"  Total IDF entries: {len(bm25.idf)}")
        print(f"  Sample IDF entries: {list(bm25.idf.items())[:5]}")
    else:
        print(f"  IDF type: {type(bm25.idf) if hasattr(bm25, 'idf') else 'NO_IDF'}")

    # Try manual scoring check
    import numpy as np
    print(f"\nQuery tokens in corpus check:")
    for token in query_tokens:
        token_in_docs = [token in doc for doc in tokenized_docs]
        print(f"  '{token}': {token_in_docs}")

    # Test BM25 parameters
    print(f"\nBM25 parameters:")
    print(f"  k1: {bm25.k1}")
    print(f"  b: {bm25.b}")
    print(f"  epsilon: {bm25.epsilon}")

    # Test with different query
    test_queries = [
        "learning",
        "machine",
        "algorithm",
        "classification",
        "neural networks"
    ]

    for test_query in test_queries:
        test_tokens = reranking_tool._tokenize(test_query)
        test_scores = bm25.get_scores(test_tokens)
        print(f"Query '{test_query}' -> tokens: {test_tokens} -> scores: {test_scores}")

if __name__ == "__main__":
    debug_bm25()