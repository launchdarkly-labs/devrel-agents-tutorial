from langchain.tools import BaseTool
from typing import List
from rank_bm25 import BM25Okapi
import re

class RerankingTool(BaseTool):
    name: str = "reranking"
    description: str = "Rerank and organize search results by relevance using BM25 algorithm. Use this when you have search results that need to be ordered by importance or relevance to the original query."
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25"""
        # Remove punctuation and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split on whitespace and filter empty strings
        return [token for token in text.split() if token.strip()]
    
    def _run(self, query=None, results=None, **kwargs) -> str:
        print(f"🔧 RERANKING TOOL INPUT:")
        print(f"   📝 Query param: '{query}' (type: {type(query)})")
        print(f"   📝 Results param: '{results}' (type: {type(results)})")
        print(f"   📝 Kwargs: {kwargs}")
        
        # Handle different input formats based on LaunchDarkly config
        # Convert query (object) to string
        if isinstance(query, dict):
            query_str = query.get('q', '') or query.get('query', '') or str(query)
        else:
            query_str = str(query) if query else ""
        
        # Convert results (array) to string
        if isinstance(results, list):
            results_str = '\n'.join([str(item) for item in results])
        else:
            results_str = str(results) if results else ""
            
        print(f"   📊 Processed query: '{query_str}'")
        print(f"   📊 Results length: {len(results_str)} characters")
        print(f"   📊 Results preview: '{results_str[:200]}...' " if results_str and len(results_str) > 200 else f"   📊 Results: '{results_str}'")
        
        # Validate inputs
        if not query_str or not results_str:
            error_msg = f"Error: Reranking requires both query and results parameters. Got query='{query_str}', results='{results_str}'"
            print(f"   ❌ RERANKING ERROR: {error_msg}")
            return error_msg
        
        # Split results into individual documents
        lines = [line.strip() for line in results_str.split('\n') if line.strip()]
        
        if not lines:
            return "No results to rerank."
        
        if len(lines) == 1:
            return f"Single result (no reranking needed):\n{lines[0]}"
        
        try:
            # Tokenize all documents for BM25
            tokenized_docs = [self._tokenize(doc) for doc in lines]
            
            # Create BM25 model
            bm25 = BM25Okapi(tokenized_docs)
            
            # Tokenize query
            query_tokens = self._tokenize(query_str)
            
            # Get BM25 scores for all documents
            scores = bm25.get_scores(query_tokens)
            
            # Pair documents with their scores
            doc_scores = list(zip(lines, scores))
            
            # Sort by BM25 score (descending)
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Format results with scores
            reranked_results = []
            for i, (doc, score) in enumerate(doc_scores, 1):
                reranked_results.append(f"{i}. [BM25: {score:.3f}] {doc}")
            
            result = f"BM25 reranked results for '{query_str}':\n\n" + '\n\n'.join(reranked_results)
            
            print(f"🔧 RERANKING TOOL OUTPUT:")
            print(f"   📊 Reranked {len(doc_scores)} documents")
            print(f"   📊 Output length: {len(result)} characters")
            print(f"   📊 Top 3 scores: {[f'{score:.3f}' for _, score in doc_scores[:3]]}")
            print(f"   📄 Output preview: '{result[:300]}...'" if len(result) > 300 else f"   📄 Full output: '{result}'")
            
            return result
            
        except Exception as e:
            print(f"ERROR: BM25 reranking failed: {e}")
            return f"Error: Reranking failed - {str(e)}"
    
