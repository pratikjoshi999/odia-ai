"""Inspect what the local retrieval layer returns for a question.

Usage from the repository root:
    PYTHONPATH=backend .venv/bin/python backend/tests/test_retrieval_questions.py
    PYTHONPATH=backend .venv/bin/python backend/tests/test_retrieval_questions.py "What is the soup city of Odisha?"

This script does not call an LLM, STT provider, or TTS provider.
"""

import sys

from app.config.settings import get_settings
from app.rag.service import get_rag_service


DEFAULT_QUESTION = "What is the soup city of Odisha?"


def inspect_question(question: str) -> None:
    settings = get_settings()
    context, score = get_rag_service().retrieve_with_score(question)
    threshold = settings.agent.rag_relevance_threshold

    print(f"Question: {question}")
    print(f"Top retrieval score: {score:.4f}")
    print(f"Configured threshold: {threshold:.4f}")
    print(f"Decision: {'GENERATE' if score >= threshold else 'OFF_TOPIC'}")
    print("\nContext returned by retrieval layer:\n")
    print(context or "No context retrieved.")


if __name__ == "__main__":
    inspect_question(DEFAULT_QUESTION)
