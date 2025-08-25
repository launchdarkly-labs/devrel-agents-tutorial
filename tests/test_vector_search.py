#!/usr/bin/env python3
"""
Test script to validate vector search vs keyword search
Enterprise AI/ML Technical Documentation
"""

import os
from dotenv import load_dotenv
from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2

load_dotenv()

def test_search_comparison():
    print("🔍 Testing Vector Search vs Keyword Search (Technical Documentation)\n")
    
    # Initialize both search tools
    search_v1 = SearchToolV1()  # Keyword search
    search_v2 = SearchToolV2()  # Vector search
    
    test_queries = [
        "reinforcement learning definition",  # Direct match: both should find it
        "temporal difference methods",        # Technical term: vector should be better
        "exploration vs exploitation",       # Conceptual: vector search advantage
        "Q-learning algorithm implementation", # Technical: should find relevant content
        "Markov decision process theory",     # Academic term: semantic search better
    ]
    
    for query in test_queries:
        print(f"🔎 Query: '{query}'")
        print("-" * 50)
        
        # Test keyword search
        print("📝 KEYWORD SEARCH (search_v1):")
        try:
            result_v1 = search_v1._run(query)
            print(result_v1[:200] + "..." if len(result_v1) > 200 else result_v1)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n🧠 VECTOR SEARCH (search_v2):")
        try:
            result_v2 = search_v2._run(query)
            print(result_v2[:300] + "..." if len(result_v2) > 300 else result_v2)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    test_search_comparison()