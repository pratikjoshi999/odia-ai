from functools import lru_cache
from pathlib import Path

from app.config.settings import Settings, get_settings
from app.rag.embeddings import get_embedding_provider
from app.rag.retriever import FaissRetriever, load_chunks


class OdishaRAGService:
    def __init__(self, settings: Settings) -> None:
        project_root = Path(__file__).resolve().parents[3]
        if settings.agent is None:
            raise RuntimeError("Agent profile is not loaded")
        data_dir = Path(settings.agent.rag_data_dir)
        if not data_dir.is_absolute():
            data_dir = project_root / data_dir
        self.retriever = FaissRetriever(load_chunks(data_dir), get_embedding_provider(settings.embedding_model))

    def retrieve(self, query: str) -> str:
        context, _ = self.retrieve_with_score(query)
        return context

    def retrieve_with_score(self, query: str) -> tuple[str, float]:
        matches = self.retriever.search_with_scores(query, top_k=get_settings().rag_top_k)
        if not matches:
            return "", 0.0
        context = "\n\n".join(f"[{chunk.source}] {chunk.text}" for chunk, _ in matches)
        return context, matches[0][1]


@lru_cache
def get_rag_service() -> OdishaRAGService:
    return OdishaRAGService(get_settings())
