from langchain_core.tools import BaseTool
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from pydantic import BaseModel, Field
import re
import json
from langchain_core.messages import ToolMessage

class RerankingInput(BaseModel):
    query: str
    results: List[Dict[str, Any]]

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
    
    def _parse_search_v2_output(self, search_output: str) -> List[Dict[str, Any]]:
        """Parse search_v2 text output format into structured results."""
        try:
            print(f"🔧 RERANKING: Parsing search_v2 output (length: {len(search_output)})")

            # Primary method: Extract JSON payload from search_v2 output
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', search_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict) and 'items' in data and data['items']:
                        print(f"🔧 RERANKING: Successfully parsed JSON payload with {len(data['items'])} items")
                        return data['items']
                    else:
                        print(f"⚠️ RERANKING: JSON payload found but no 'items' field or empty items")
                except json.JSONDecodeError as je:
                    print(f"⚠️ RERANKING: JSON decode error: {je}")

            # Fallback 1: Try to find JSON block anywhere in the text (more flexible)
            json_blocks = re.findall(r'\{[^{}]*"items"[^{}]*\[[^\]]*\][^{}]*\}', search_output, re.DOTALL)
            for json_block in json_blocks:
                try:
                    data = json.loads(json_block)
                    if isinstance(data, dict) and 'items' in data and data['items']:
                        print(f"🔧 RERANKING: Successfully parsed loose JSON block with {len(data['items'])} items")
                        return data['items']
                except json.JSONDecodeError:
                    continue

            # Fallback 2: Search_v2 returns format like: "Found N relevant document(s):\n[Relevance: 0.454] content..."
            relevance_entries = re.findall(r'\[Relevance: ([\d.]+)\] (.+?)(?=\[Relevance:|$)', search_output, re.DOTALL)

            if relevance_entries:
                search_results = []
                for i, (score, content) in enumerate(relevance_entries):
                    search_results.append({
                        "text": content.strip(),
                        "score": float(score),
                        "metadata": {"source": "search_v2", "rank": i+1}
                    })
                print(f"🔧 RERANKING: Successfully parsed {len(search_results)} items from relevance format")
                return search_results
            else:
                print(f"⚠️ RERANKING: Could not parse search_v2 format. Preview: {search_output[:300]}...")
                return []

        except Exception as e:
            print(f"⚠️ RERANKING: Error parsing search_v2 output: {e}")
            return []

    def _extract_items_from_string(self, results_str: str) -> List[Dict[str, Any]]:
        """Extract JSON items array from fenced JSON string if needed."""
        try:
            # Try to find fenced JSON block
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', results_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                if isinstance(data, dict) and 'items' in data:
                    return data['items']
            # If no fenced JSON, maybe it's just a JSON string
            data = json.loads(results_str)
            if isinstance(data, dict) and 'items' in data:
                return data['items']
            elif isinstance(data, list):
                return data
        except (json.JSONDecodeError, AttributeError):
            pass
        return []


    def _run(self, query: str, results: List[Dict[str, Any]], **kwargs) -> str:
        print(f"🔧 RERANKING: Got array results directly ({len(results)} items)")
        items = results
        
        # Validate inputs
        if not query:
            return "ERROR: `query` parameter is required."
        
        if not isinstance(items, list) or not items:
            return "ERROR: `results` must be a non-empty list of search result items from search_v2."
        
        print(f"🔧 RERANKING: Query='{query}', Items={len(items)}")
        
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
            print(f"🔧 RERANKING COMPLETE: {len(item_scores)} items reranked")
            return result
            
        except Exception as e:
            print(f"ERROR: BM25 reranking failed: {e}")
            return f"Error: Reranking failed - {str(e)}"
    
