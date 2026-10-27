from abc import ABC, abstractmethod
import hashlib
import re

import numpy as np


class EmbeddingProvider(ABC):
    dimension = 512

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class HashingEmbeddingProvider(EmbeddingProvider):
    """Dependency-light baseline embedding; replaceable by a multilingual model later."""

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
            tokens += [text[index : index + 3] for index in range(max(0, len(text) - 2))]
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest, "little") % self.dimension
                vectors[row, index] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)


def get_embedding_provider(model: str) -> EmbeddingProvider:
    if model == "hashing-v1":
        return HashingEmbeddingProvider()
    raise ValueError(f"Unsupported embedding model: {model}")

