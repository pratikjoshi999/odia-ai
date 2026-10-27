from collections.abc import Sequence
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.chat import ConversationMessage
from app.rag.service import OdishaRAGService
from app.services.llm import LLMProvider
from app.services.language import LanguageCode, detect_language
from app.utils.observability import current_metrics, log_event, measure

OFF_TOPIC_REPLY = (
    "ମୁଁ ବର୍ତ୍ତମାନ ଓଡ଼ିଶା ସମ୍ବନ୍ଧୀୟ ସୂଚନା ଦେବା ପାଇଁ ତିଆରି ହୋଇଛି। "
    "ଆପଣ ଓଡ଼ିଶାର ପର୍ଯ୍ୟଟନ, ଇତିହାସ, ସଂସ୍କୃତି କିମ୍ବା ଅନ୍ୟାନ୍ୟ ବିଷୟରେ ପଚାରିପାରିବେ।"
)
OFF_TOPIC_REPLY_EN = (
    "I am currently designed to provide information related to Odisha. "
    "You can ask me about Odisha's tourism, history, culture, geography, or other Odisha-related topics."
)
DOMAIN_TERMS = (
    "odisha", "odissa", "ଓଡ଼ିଶା", "ଓଡିଶା", "ପୁରୀ", "puri", "ଭୁବନେଶ୍ୱର", "bhubaneswar",
    "କଟକ", "cuttack", "କୋଣାର୍କ", "konark", "ଜଗନ୍ନାଥ", "jagannath", "ଓଡ଼ିଆ", "odia",
    "କଳିଙ୍ଗ", "kalinga", "ଚିଲିକା", "chilika", "ସିମିଳିପାଳ", "similipal",
)
GREETING_TERMS = ("ନମସ୍କାର", "ନମସ୍କାର୍", "hello", "hi", "ହେଲୋ", "ନମୋସ୍କାର")


class ConversationState(TypedDict, total=False):
    message: str
    history: Sequence[ConversationMessage]
    intent: Literal["odisha", "off_topic", "unknown"]
    reply: str
    provider: str
    context: str
    language: LanguageCode
    domain_terms: Sequence[str]
    off_topic_reply: str
    off_topic_reply_en: str
    rag_relevance_threshold: float
    retrieval_score: float


def classify_node(state: ConversationState) -> ConversationState:
    message = state["message"].casefold()
    domain_terms = state.get("domain_terms", DOMAIN_TERMS)
    is_in_scope = any(term.casefold() in message for term in domain_terms)
    is_greeting = any(term.casefold() in message for term in GREETING_TERMS)
    history = state.get("history", ())
    last_message = history[-1] if history else None
    is_follow_up = (
        bool(last_message and last_message.role == "assistant" and ("?" in last_message.text or "？" in last_message.text))
        and len(message.split()) <= 12
    )
    intent = "odisha" if is_in_scope or is_greeting or is_follow_up else "unknown"
    language = detect_language(state["message"])
    log_event("agent_state", state="classify", intent=intent, language=language, follow_up=is_follow_up)
    return {"intent": intent, "language": language}


def route_intent(state: ConversationState) -> str:
    return "retrieve" if state.get("intent") == "unknown" else ("generate" if state.get("intent") == "odisha" else "guard")


def route_retrieval(state: ConversationState) -> str:
    threshold = state.get("rag_relevance_threshold", 0.25)
    return "generate" if state.get("retrieval_score", 0.0) >= threshold else "guard"


def guard_node(state: ConversationState) -> ConversationState:
    reply = state.get("off_topic_reply", OFF_TOPIC_REPLY) if state.get("language", "od-IN") == "od-IN" else state.get("off_topic_reply_en", OFF_TOPIC_REPLY_EN)
    log_event("agent_state", state="guard", language=state.get("language", "od-IN"))
    return {"reply": reply, "provider": "policy"}


def retrieval_node(rag: OdishaRAGService):
    def retrieve(state: ConversationState) -> ConversationState:
        log_event("agent_state", state="retrieve", top_level="odisha")
        with measure("rag_latency_ms"):
            context, score = rag.retrieve_with_score(state["message"])
        log_event("rag_complete", context_chars=len(context))
        log_event("agent_state", state="domain_gate", retrieval_score=round(score, 4))
        return {"context": context, "retrieval_score": score}

    return retrieve


def response_node(provider: LLMProvider):
    async def generate_node(state: ConversationState) -> ConversationState:
        language = state.get("language", "od-IN")
        log_event("llm_call_started", provider=provider.name, language=language, history_count=len(state.get("history", ())), context_chars=len(state.get("context", "")))
        try:
            with measure("llm_latency_ms"):
                reply = await provider.generate(state["message"], state.get("history", ()), state.get("context", ""), language)
        except Exception as exc:
            log_event("llm_call_failed", provider=provider.name, error_type=type(exc).__name__)
            raise
        log_event("llm_call_completed", provider=provider.name, reply_chars=len(reply))
        metrics = current_metrics()
        if metrics:
            metrics.metadata["llm_provider"] = provider.name
        return {"reply": reply, "provider": provider.name}

    return generate_node


def validate_node(state: ConversationState) -> ConversationState:
    reply = state.get("reply", "").strip()
    if not reply or len(reply) > 12000:
        log_event("agent_state", state="validate", result="fallback")
        return {"reply": "କ୍ଷମା କରିବେ, ଏହି ପ୍ରଶ୍ନର ଉତ୍ତର ଏବେ ଦେଇପାରୁନାହିଁ।", "provider": "validation"}
    log_event("agent_state", state="validate", result="accepted")
    return {"reply": reply}


def build_conversation_graph(provider: LLMProvider, rag: OdishaRAGService):
    graph = StateGraph(ConversationState)
    graph.add_node("classify", classify_node)
    graph.add_node("generate", response_node(provider))
    graph.add_node("retrieve", retrieval_node(rag))
    graph.add_node("guard", guard_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_intent, {"retrieve": "retrieve", "generate": "generate", "guard": "guard"})
    graph.add_conditional_edges("retrieve", route_retrieval, {"generate": "generate", "guard": "guard"})
    graph.add_edge("generate", "validate")
    graph.add_edge("guard", "validate")
    graph.add_edge("validate", END)
    return graph.compile()
