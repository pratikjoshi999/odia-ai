from dataclasses import dataclass
from pathlib import Path
import re

import faiss
import numpy as np

from app.rag.embeddings import EmbeddingProvider


SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "can", "do", "for", "how", "i", "in",
    "is", "it", "of", "on", "the", "to", "what", "where", "who", "which", "with",
}


@dataclass(frozen=True)
class DocumentChunk:
    source: str
    text: str


def _search_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        if token not in SEARCH_STOPWORDS and len(token) > 1
    }


def _keyword_score(query: str, document: str) -> float:
    query_tokens = _search_tokens(query)
    if not query_tokens:
        return 0.0
    document_tokens = _search_tokens(document)
    overlap_score = len(query_tokens & document_tokens) / len(query_tokens)
    normalized_query = " ".join(query.casefold().split())
    normalized_document = " ".join(document.casefold().split())
    phrase_bonus = 0.2 if len(query_tokens) > 1 and normalized_query in normalized_document else 0.0
    return min(1.0, overlap_score + phrase_bonus)


def load_chunks(data_dir: Path, words_per_chunk: int = 120) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for path in sorted(data_dir.glob("*.txt")):
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n+", path.read_text(encoding="utf-8"))
            if paragraph.strip()
        ]
        for paragraph in paragraphs:
            words = paragraph.split()
            for start in range(0, len(words), words_per_chunk):
                text = " ".join(words[start : start + words_per_chunk]).strip()
                if text:
                    chunks.append(DocumentChunk(source=path.name, text=text))
    return chunks


class FaissRetriever:
    def __init__(self, chunks: list[DocumentChunk], embedder: EmbeddingProvider) -> None:
        if not chunks:
            raise ValueError("The agent knowledge base is empty")
        self.chunks = chunks
        self.embedder = embedder
        vectors = embedder.embed([chunk.text for chunk in chunks])
        self.index = faiss.IndexFlatIP(embedder.dimension)
        self.index.add(np.ascontiguousarray(vectors))

    def search_with_scores(self, query: str, top_k: int = 4) -> list[tuple[DocumentChunk, float]]:
        if not query.strip():
            return []
        query_vector = np.ascontiguousarray(self.embedder.embed([query]))
        candidate_k = min(max(top_k * 4, top_k), len(self.chunks))
        scores, indices = self.index.search(query_vector, candidate_k)
        candidates = [
            (self.chunks[index], float(scores[0][position]))
            for position, index in enumerate(indices[0])
            if index >= 0
        ]
        ranked = [
            (chunk, (0.6 * _keyword_score(query, chunk.text)) + (0.4 * max(vector_score, 0.0)))
            for chunk, vector_score in candidates
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]

    def search(self, query: str, top_k: int = 4) -> list[DocumentChunk]:
        return [chunk for chunk, _ in self.search_with_scores(query, top_k)]
