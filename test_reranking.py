#!/usr/bin/env python3
"""
Test script to verify reranking tool functionality
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from tools_impl.reranking import RerankingTool

def test_reranking():
    """Test the reranking tool with sample data"""

    # Create reranking tool instance
    reranking_tool = RerankingTool()

    # Test data
    query = "machine learning algorithms"
    sample_results = [
        {"text": "Deep learning is a subset of machine learning with neural networks", "score": 0.8},
        {"text": "Random forest is a popular machine learning algorithm for classification", "score": 0.7},
        {"text": "Linear regression is a simple statistical method", "score": 0.6},
        {"text": "Support vector machines are effective for classification tasks", "score": 0.5}
    ]

    print(f"Testing reranking tool with query: '{query}'")
    print(f"Input results: {len(sample_results)} items")

    # Test the reranking
    try:
        result = reranking_tool._run(query=query, results=sample_results)
        print("\n=== RERANKING RESULT ===")
        print(result)
        print("\n=== TEST PASSED ===")
        return True

    except Exception as e:
        print(f"\n=== TEST FAILED ===")
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_reranking()