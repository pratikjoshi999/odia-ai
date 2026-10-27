import asyncio

from app.agents.conversation import build_conversation_graph, classify_node
from app.config.settings import get_settings
from app.models.chat import ConversationMessage


class FakeRag:
    def __init__(self, score: float) -> None:
        self.score = score

    def retrieve_with_score(self, query: str) -> tuple[str, float]:
        return "knowledge context", self.score


class FakeProvider:
    name = "fake"

    async def generate(self, message, history=(), context="", language="od-IN") -> str:
        return f"generated: {message}"


def test_short_follow_up_is_in_scope() -> None:
    settings = get_settings()
    result = classify_node({
        "message": "Yes",
        "history": [ConversationMessage(role="assistant", text="Would you like to know more?")],
        "domain_terms": settings.agent.domain_terms,
    })
    assert result["intent"] == "odisha"


def test_unknown_query_is_deferred_to_retrieval() -> None:
    settings = get_settings()
    result = classify_node({"message": "How do I cook pasta?", "history": [], "domain_terms": settings.agent.domain_terms})
    assert result["intent"] == "unknown"


def invoke_graph(score: float) -> dict:
    settings = get_settings()
    graph = build_conversation_graph(FakeProvider(), FakeRag(score))
    return asyncio.run(graph.ainvoke({
        "message": "How do I cook pasta?",
        "history": [],
        "domain_terms": settings.agent.domain_terms,
        "off_topic_reply": settings.agent.off_topic_reply,
        "off_topic_reply_en": settings.agent.off_topic_reply_en,
        "rag_relevance_threshold": 0.25,
    }))


def test_low_retrieval_confidence_uses_policy_reply() -> None:
    assert invoke_graph(0.10)["provider"] == "policy"


def test_high_retrieval_confidence_generates_response() -> None:
    assert invoke_graph(0.80)["provider"] == "fake"
