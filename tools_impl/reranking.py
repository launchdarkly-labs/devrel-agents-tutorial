from langchain_core.tools import BaseTool
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from pydantic import BaseModel, Field
import re
import json

class RerankingInput(BaseModel):
    query: str
    results: Optional[List[Dict[str, Any]]] = None

class RerankingTool(BaseTool):
    name: str = "reranking"
    description: str = "Reorders results by relevance using BM25 algorithm"
    args_schema: type[BaseModel] = RerankingInput
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25"""
        # Remove punctuation and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split on whitespace and filter empty strings
        return [token for token in text.split() if token.strip()]

    def _parse_search_results_from_messages(self, kwargs) -> List[Dict[str, Any]]:
        """Parse search_v2 results from ToolMessages when LLM doesn't extract them directly"""
        try:
            # Try to get messages from various possible kwargs keys
            messages = kwargs.get('messages', []) or kwargs.get('chat_history', [])

            # Look for most recent search_v2 ToolMessage in reverse order
            for message in reversed(messages):
                if hasattr(message, 'content') and isinstance(message.content, str):
                    content = message.content
                    # Look for JSON block in search_v2 output
                    if '```json' in content and 'items' in content:
                        try:
                            # Extract JSON from fenced code block
                            json_start = content.find('```json') + 7
                            json_end = content.find('```', json_start)
                            if json_end > json_start:
                                json_str = content[json_start:json_end].strip()
                                search_data = json.loads(json_str)
                                if isinstance(search_data, dict) and 'items' in search_data:
                                    return search_data['items']
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            return []
        except Exception:
            return []
    



    def _run(self, query: str, results: List[Dict[str, Any]] = None, **kwargs) -> str:
        # Handle LLM-mediated tool chaining: LLM should extract results from search_v2 ToolMessage
        if results is None or not results:
            # Fallback: parse recent messages to find search_v2 JSON results
            items = self._parse_search_results_from_messages(kwargs)
            if not items:
                return f"No search results found. Please run search_v2 with query '{query}' first."
        else:
            # LLM successfully extracted and passed results directly
            items = results

        # Validate inputs
        if not query:
            return "ERROR: `query` parameter is required."

        if not isinstance(items, list) or not items:
            return "ERROR: `results` must be a non-empty list of search result items from search_v2."
        
        # Extract text content from each item
        docs = []
        for item in items:
            if isinstance(item, dict) and 'text' in item:
                docs.append(item['text'])
            elif isinstance(item, str):
                docs.append(item)
            else:
                docs.append(str(item))
        
        if len(docs) == 1:
            return f"Single result (no reranking needed):\n[BM25: N/A] {docs[0]}"
        
        try:
            # Tokenize all documents for BM25
            tokenized_docs = [self._tokenize(doc) for doc in docs]
            
            # Create BM25 model
            bm25 = BM25Okapi(tokenized_docs)
            
            # Tokenize query
            query_tokens = self._tokenize(query)
            
            # Get BM25 scores for all documents
            scores = bm25.get_scores(query_tokens)
            
            # Pair items with their BM25 scores
            item_scores = list(zip(items, scores))
            
            # Sort by BM25 score (descending)
            item_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Format results with scores
            reranked_results = []
            for i, (item, score) in enumerate(item_scores, 1):
                if isinstance(item, dict):
                    text = item.get('text', str(item))
                    orig_score = item.get('score', 'N/A')
                    metadata = item.get('metadata', {})
                    reranked_results.append(
                        f"{i}. [BM25: {score:.3f}, Orig: {orig_score}] {text}"
                    )
                else:
                    reranked_results.append(f"{i}. [BM25: {score:.3f}] {item}")
            
            result = f"BM25 reranked results for '{query}':\n\n" + '\n\n'.join(reranked_results)
            return result
            
        except Exception as e:
            print(f"ERROR: BM25 reranking failed: {e}")
            return f"Error: Reranking failed - {str(e)}"
    
