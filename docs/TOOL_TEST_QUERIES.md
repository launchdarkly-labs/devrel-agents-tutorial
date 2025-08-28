# Tool Testing Queries

## Basic Tool Testing (docs-only variation)
### Tests: search_v2 only

What information do you have about machine learning in your knowledge base?

---

Search your documentation for reinforcement learning concepts

---

Find any content about neural networks in your internal documents

---

## RAG Stack Testing (rag-enabled variation)
### Tests: search_v2 + reranking

What are the most relevant machine learning techniques mentioned in your knowledge base?

---

Find the best matches for "deep learning algorithms" in your documentation

---

Search for "transformer architectures" and rank the results by relevance

---

## MCP ArXiv Testing (research-enhanced variation)
### Tests: arxiv_search tool

Find recent ArXiv papers on reinforcement learning from the last 6 months

---

Search ArXiv for papers about "graph neural networks" published in 2024

---

Look for ArXiv papers on "multimodal learning" in the cs.AI category

---

## MCP Semantic Scholar Testing (research-enhanced variation)
### Tests: semantic_scholar tool

Search Semantic Scholar for papers on "federated learning"

---

Find academic papers about "attention mechanisms" with author details

---

Look up citation networks for "transformer models" research

---

## Full Stack Testing (research-enhanced variation)
### Tests: search_v2 + reranking + arxiv_search + semantic_scholar

Compare what you know about transformers from your knowledge base with recent ArXiv and Semantic Scholar papers

---

Find information about reinforcement learning from both your internal docs and external academic sources

---

Search for "computer vision" across your knowledge base, ArXiv, and academic databases

---

## Tool Chain Testing
### Tests multiple tool calls in sequence

First search your knowledge base for "machine learning", then find related papers on ArXiv

---

Look up "neural architecture search" in your docs, then find academic citations on Semantic Scholar

---

Search for "multi-agent systems" internally and externally, then rerank all results

---

## Performance Testing
### Tests tool limits and performance

Find comprehensive information about "artificial intelligence" using all available search methods

---

Search for "deep reinforcement learning" and provide results from multiple sources

---

Look for "generative models" across all your research tools and databases

---

## Error Handling Testing
### Tests tool fallbacks and error cases

Search for "nonexistent_technical_term_xyz123" across all sources

---

Find papers about "made_up_algorithm_name" in academic databases

---

Look for "invalid_search_query_test" in your knowledge base and external sources