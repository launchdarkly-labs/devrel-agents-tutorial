from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from pydantic import BaseModel
from functools import lru_cache

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
    filtered = [(d, s, m) for (d, s, m) in raw if s >= min_score]
    return filtered[:top_k]


# ---------- Tool ----------
class SearchToolV2(BaseTool):
    """Advanced vector-based semantic search through enterprise documentation."""
    name: str = "search_v2"
    description: str = "Semantic search using vector embeddings"
    args_schema: type[BaseModel] = SearchV2Input

    def _run(self, query: str, top_k: int = 3, **kwargs: Any) -> str:
        try:
            # clamp for safety (in case someone bypasses args_schema)
            top_k = max(1, min(int(top_k), 20))
            min_score = 0.20  # Default minimum similarity score

            results = _cached_search(query, top_k, min_score)

            if not results:
                return "No relevant documentation found for your query."

            # Build concise human summary
            summary_lines = [f"📚 Found {len(results)} relevant document(s):\n"]
            for idx, (doc, score, _metadata) in enumerate(results, 1):
                snippet = (doc or "").strip().replace("\n", " ")
                if len(snippet) > 800:
                    snippet = snippet[:800] + "..."

                summary_lines.append(f"{idx}. [Score: {score:.2f}]")
                summary_lines.append(f"   {snippet}\n")

            return "\n".join(summary_lines) + f"\n---\n_Found {len(results)} results for: \"{query}\"_"

        except RuntimeError as e:
            # Embeddings not initialized, or explicit init errors
            return f"Search error: {e}"
        except Exception as e:
            # Generic safety net; keep message concise for tool consumption
            return (
                f"Search error: {e}. "
                "If this persists, ensure vector embeddings are initialized with `uv run initialize_embeddings.py`."
            )
