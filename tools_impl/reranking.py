from langchain_core.tools import BaseTool
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from pydantic import BaseModel
import re

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
        return text.split()

    def _run(self, query: str, results: List[Dict[str, Any]] = None, **kwargs) -> str:
        # The LLM chains the tools: it passes the search_v2 results it received as `results`
        if not results:
            return f"No search results found. Please run search_v2 with query '{query}' first."
        items = results

        # Extract text content from each item
        docs = []
        for item in items:
            if isinstance(item, dict) and 'text' in item:
                docs.append(item['text'])
            else:
                docs.append(str(item))

        if len(docs) == 1:
            return f"Single result (no reranking needed):\n[BM25: N/A] {docs[0]}"

        try:
            tokenized_docs = [self._tokenize(doc) for doc in docs]
            bm25 = BM25Okapi(tokenized_docs)
            query_tokens = self._tokenize(query)
            scores = bm25.get_scores(query_tokens)

            # Handle small corpus issue: if all scores are 0, use simple term frequency scoring
            if all(score == 0.0 for score in scores):
                # Count query token matches, normalized by document length to favor focused documents
                scores = [
                    sum(1 for token in query_tokens if token in doc_tokens) / len(doc_tokens) if doc_tokens else 0.0
                    for doc_tokens in tokenized_docs
                ]

            # Sort items by score (descending)
            item_scores = sorted(zip(items, scores), key=lambda x: x[1], reverse=True)

            # Format results with scores
            reranked_results = []
            for i, (item, score) in enumerate(item_scores, 1):
                if isinstance(item, dict):
                    text = item.get('text', str(item))
                    orig_score = item.get('score', 'N/A')
                    reranked_results.append(
                        f"{i}. [BM25: {score:.3f}, Orig: {orig_score}] {text}"
                    )
                else:
                    reranked_results.append(f"{i}. [BM25: {score:.3f}] {item}")

            return f"BM25 reranked results for '{query}':\n\n" + '\n\n'.join(reranked_results)

        except Exception as e:
            print(f"ERROR: BM25 reranking failed: {e}")
            return f"Error: Reranking failed - {str(e)}"
