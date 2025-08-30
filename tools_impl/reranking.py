from langchain.tools import BaseTool
from typing import List
from rank_bm25 import BM25Okapi
import re

class RerankingTool(BaseTool):
    name: str = "reranking"
    description: str = "Rerank search results using BM25 algorithm for better relevance ordering. IMPORTANT: This tool requires two parameters: 'query' (the search query) and 'results' (the actual search results text from search_v2). Only call this tool AFTER you have search results to rerank."
    
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
        
        # If no results provided, look for recent search results in the conversation
        # This is the KEY FIX - extract from LangChain conversation history
        if not results_str:
            print("   🔍 SEARCHING FOR PREVIOUS SEARCH RESULTS...")
            
            # Get message contents from kwargs (simple list of strings)
            message_contents = kwargs.get('message_contents', [])
            
            # Look through recent message contents for search results
            found_results = False
            for content in reversed(message_contents):  # Search backwards through conversation
                try:
                    if content and isinstance(content, str):
                        print(f"   🔍 CHECKING CONTENT: {content[:100]}...")
                        
                        # Look SPECIFICALLY for ToolMessage content with search results (NOT AI messages)
                        if ('found 3 relevant documents' in content.lower() or 
                            'found 2 relevant documents' in content.lower() or
                            'found 1 relevant documents' in content.lower()) and '[relevance:' in content.lower():
                            # This is actual search results from search_v2 tool
                            results_str = content
                            print(f"   ✅ FOUND ACTUAL SEARCH RESULTS: {len(results_str)} chars")
                            found_results = True
                            break
                        elif content.startswith("Now, I'll rerank") or "try one more" in content.lower():
                            # Skip AI agent messages about reranking - these are not search results
                            print(f"   ⏭️  SKIPPING AI MESSAGE: {content[:50]}...")
                            continue
                except Exception as e:
                    print(f"   ⚠️ Error processing message content: {e}")
                    continue
            
            if not found_results:
                print("   ❌ NO SEARCH RESULTS FOUND in conversation history")
        
        # If still no results, provide a helpful message for the agent
        if not results_str:
            return "ERROR: No search results found to rerank. This tool requires search results from search_v2. Please call search_v2 first to get search results, then the reranking tool can access them from the conversation history."
            
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
    
