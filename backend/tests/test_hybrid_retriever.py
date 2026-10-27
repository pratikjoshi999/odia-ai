from app.rag.embeddings import HashingEmbeddingProvider
from app.rag.retriever import DocumentChunk, FaissRetriever


def test_exact_terms_rerank_the_relevant_chunk() -> None:
    chunks = [
        DocumentChunk("unrelated.txt", "Odisha has many historic cities and landmarks."),
        DocumentChunk("food.txt", "Nuapada is known as the Soup City of Odisha."),
    ]
    retriever = FaissRetriever(chunks, HashingEmbeddingProvider())

    results = retriever.search_with_scores("What is the soup city of Odisha?", top_k=2)

    assert results[0][0].source == "food.txt"
    assert results[0][1] > results[1][1]
