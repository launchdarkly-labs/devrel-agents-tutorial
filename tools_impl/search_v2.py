from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from pydantic import BaseModel, Field, field_validator
from functools import lru_cache

# IMPORTANT: use langchain_core.tools for LC 0.2+
from langchain_core.tools import BaseTool

from data.vector_store import VectorStore


# ---------- Minimal Input schema (LaunchDarkly provides full schema) ----------
class SearchV2Input(BaseModel):
    query: str
    top_k: Optional[int] = 3


# ---------- Vector store singleton ----------
_VECTOR_STORE: VectorStore | None = None

def _get_vector_store() -> VectorStore:
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        vs = VectorStore()
        if not vs.exists():
            # Keep this explicit; better to fail here than pretend to search nothing.
            raise RuntimeError(
                "Vector embeddings not initialized. Run `uv run initialize_embeddings.py` first."
            )
        _VECTOR_STORE = vs
    return _VECTOR_STORE


# ---------- Small cache to avoid repeated identical calls ----------
# Cache key is (query, top_k, min_score)
@lru_cache(maxsize=128)
def _cached_search(query: str, top_k: int, min_score: float) -> List[Tuple[str, float, Dict]]:
    vs = _get_vector_store()
    # We ask store for a few extra and then threshold+trim, helps when many are < min_score
    raw = vs.search(query, top_k=min(top_k * 2, 50))
    # raw items expected as (doc_text, score, metadata)
    filtered = [(d, s, m) for (d, s, m) in raw if isinstance(s, (int, float)) and s >= min_score]
    return filtered[:top_k]


# ---------- Tool ----------
class SearchToolV2(BaseTool):
    """Advanced vector-based semantic search through enterprise documentation."""
    name: str = "search_v2"
    description: str = "Semantic search using vector embeddings"
    args_schema: type[BaseModel] = SearchV2Input

    # exclude heavy objects from Pydantic serialization
    vector_store: Any = Field(default=None, exclude=True)

    def __init__(self, **data: Any):
        super().__init__(**data)
        # Lazy init; will raise a clean error on first use if uninitialized
        self.vector_store = None

    def _run(self, query: str, top_k: int = 3, **kwargs) -> str:
        try:
            # clamp for safety (in case someone bypasses args_schema)
            top_k = max(1, min(int(top_k), 20))
            min_score = 0.20  # Default minimum similarity score

            results = _cached_search(query, top_k, min_score)

            if not results:
                return (
                    "No relevant documentation found for your query.\n\n"
                    f"```json\n{{\n"
                    f"  \"query\": {query!r},\n"
                    f"  \"top_k\": {top_k},\n"
                    f"  \"min_score\": {min_score},\n"
                    f"  \"count\": 0,\n"
                    f"  \"items\": []\n"
                    f"}}\n```"
                )

            # Build concise human summary + machine-readable JSON
            summary_lines = [f"📚 Found {len(results)} relevant document(s):\n"]
            items = []
            for idx, (doc, score, metadata) in enumerate(results, 1):
                # brief snippet for readability - shortened to 200 chars
                snippet = (doc or "").strip().replace("\n", " ")
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                
                # Format more cleanly with number and indentation
                summary_lines.append(f"{idx}. [Score: {score:.2f}]")
                summary_lines.append(f"   {snippet}\n")
                
                items.append({
                    "text": (doc or ""),
                    "score": float(score),
                    "metadata": metadata or {}
                })

            payload = {
                "query": query,
                "top_k": top_k,
                "min_score": min_score,
                "count": len(items),
                "items": items
            }

            # Return: clean human summary + compact JSON footer for tool chaining
            return "\n".join(summary_lines) + f"\n---\n_Found {len(items)} results for: \"{query}\"_"

        except RuntimeError as e:
            # Embeddings not initialized, or explicit init errors
            return f"Search error: {e}"
        except Exception as e:
            # Generic safety net; keep message concise for tool consumption
            return (
                f"Search error: {e}. "
                "If this persists, ensure vector embeddings are initialized with `uv run initialize_embeddings.py`."
            )
