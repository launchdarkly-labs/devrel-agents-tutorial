#!/usr/bin/env python3
"""
Test script to validate vector search vs keyword search
"""

from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2

def test_search_comparison():
    print("🔍 Testing Vector Search vs Keyword Search\n")
    
    # Initialize both search tools
    search_v1 = SearchToolV1()  # Keyword search
    search_v2 = SearchToolV2()  # Vector search
    
    test_queries = [
        "phoenix combustion problems",  # Semantic: should find phoenix rebirth/fire content
        "dragon feeding",              # Direct match: both should find it
        "stubborn unicorn behavior",   # Semantic: should find unicorn training content  
        "pet insurance for magical creatures",  # Semantic: should find insurance content
        "rebirth cycles",             # Semantic: should find phoenix content
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