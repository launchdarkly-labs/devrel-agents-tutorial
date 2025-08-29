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
    
    def _run(self, query: str, results: str) -> str:
        print(f"DEBUG: BM25 RerankingTool called with query='{query[:50]}...', results='{results[:100]}...'")
        
        # Validate inputs
        if not query or not results:
            return "Error: Reranking requires both query and results parameters."
        
        # Split results into individual documents
        lines = [line.strip() for line in results.split('\n') if line.strip()]
        
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
            query_tokens = self._tokenize(query)
            
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
            
            result = f"BM25 reranked results for '{query}':\n\n" + '\n\n'.join(reranked_results)
            print(f"DEBUG: BM25 RerankingTool returning: {result[:150]}...")
            return result
            
        except Exception as e:
            print(f"ERROR: BM25 reranking failed: {e}")
            return f"Error: Reranking failed - {str(e)}"
    
