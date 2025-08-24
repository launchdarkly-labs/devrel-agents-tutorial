from langchain.tools import BaseTool
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from data.mythical_pets_kb import MYTHICAL_PETS_KB

class SearchToolV2(BaseTool):
    name: str = "search_vector"
    description: str = "Advanced vector-based semantic search through mythical pet care documentation"
    
    def _run(self, query: str) -> str:
        docs = MYTHICAL_PETS_KB
        
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        doc_vectors = vectorizer.fit_transform(docs)
        query_vector = vectorizer.transform([query])
        
        similarities = cosine_similarity(query_vector, doc_vectors).flatten()
        
        doc_scores = list(zip(docs, similarities))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        relevant_docs = [doc for doc, score in doc_scores if score > 0.1]
        
        if not relevant_docs:
            return "No relevant documentation found for your query."
        
        top_results = relevant_docs[:3]
        scores = [score for _, score in doc_scores[:len(top_results)]]
        
        result = f"Found {len(relevant_docs)} relevant documents (showing top {len(top_results)}):\n\n"
        for i, _ in enumerate(top_results):
            result += f"[Relevance: {scores[i]:.3f}] {top_results[i]}\n\n"
        
        return result