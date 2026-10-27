from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.config.settings import Settings, get_settings
from app.agents.conversation import build_conversation_graph
from app.models.chat import ChatRequest, ChatResponse
from app.models.config import AgentConfigResponse
from app.models.speech import SpeechToTextResponse
from app.models.tts import TextToSpeechRequest
from app.rag.service import OdishaRAGService, get_rag_service
from app.services.stt import SpeechToTextError, SpeechToTextService, get_stt_service
from app.services.tts import TextToSpeechError, TextToSpeechService, get_tts_service
from app.services.llm import LLMProvider, get_llm_provider
from app.utils.observability import current_metrics, log_event, measure

router = APIRouter(prefix="/api")


def provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    return get_llm_provider(settings)


def rag_service() -> OdishaRAGService:
    return get_rag_service()


def stt_service(settings: Settings = Depends(get_settings)) -> SpeechToTextService:
    return get_stt_service(settings)


def tts_service(settings: Settings = Depends(get_settings)) -> TextToSpeechService:
    return get_tts_service(settings)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, llm: LLMProvider = Depends(provider), rag: OdishaRAGService = Depends(rag_service)) -> ChatResponse:
    log_event("chat_received", message_chars=len(request.message), history_count=len(request.history))
    try:
        graph = build_conversation_graph(llm, rag)
        settings = get_settings()
        if settings.agent is None:
            raise RuntimeError("Agent profile is not loaded")
        result = await graph.ainvoke({
            "message": request.message.strip(),
            "history": request.history,
            "domain_terms": tuple(settings.agent.domain_terms),
            "off_topic_reply": settings.agent.off_topic_reply,
            "off_topic_reply_en": settings.agent.off_topic_reply_en,
            "rag_relevance_threshold": settings.agent.rag_relevance_threshold,
        })
    except Exception as exc:
        if metrics := current_metrics():
            metrics.record_error("chat")
        raise HTTPException(status_code=502, detail="The assistant is temporarily unavailable.") from exc
    return ChatResponse(reply=result["reply"], provider=result["provider"], request_id=str(uuid4()), language=result.get("language", "od-IN"))


@router.get("/config", response_model=AgentConfigResponse)
async def agent_config(settings: Settings = Depends(get_settings)) -> AgentConfigResponse:
    if settings.agent is None:
        raise HTTPException(status_code=500, detail="Agent profile is not loaded")
    return AgentConfigResponse(id=settings.agent.id, name=settings.agent.name, tagline=settings.agent.tagline)


@router.post("/stt", response_model=SpeechToTextResponse)
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    stt: SpeechToTextService = Depends(stt_service),
) -> SpeechToTextResponse:
    log_event("stt_received", requested_language=language or settings.stt_language)
    allowed_types = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/aac", "audio/flac"}
    content_type = (audio.content_type or "").split(";", 1)[0].lower()
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="ସମର୍ଥିତ ଅଡିଓ ଫର୍ମାଟ୍ ବ୍ୟବହାର କରନ୍ତୁ।")
    payload = await audio.read(settings.stt_max_audio_bytes + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="ଖାଲି ଅଡିଓ ପଠାଯାଇଛି।")
    if len(payload) > settings.stt_max_audio_bytes:
        raise HTTPException(status_code=413, detail="ଅଡିଓ ଫାଇଲ୍ ବହୁତ ବଡ଼।")
    if language is not None and language not in {"od-IN", "en-IN"}:
        raise HTTPException(status_code=400, detail="ସମର୍ଥିତ ଭାଷା ବାଛନ୍ତୁ।")
    try:
        with measure("stt_latency_ms"):
            result = await stt.transcribe(payload, audio.filename or "recording.webm", content_type, language)
    except SpeechToTextError as exc:
        if metrics := current_metrics():
            metrics.record_error("stt")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log_event("stt_completed", language=result.language, transcript_chars=len(result.text))
    return SpeechToTextResponse(text=result.text, language=result.language, confidence=result.confidence)


@router.post("/tts")
async def text_to_speech(
    request: TextToSpeechRequest,
    tts: TextToSpeechService = Depends(tts_service),
) -> Response:
    log_event("tts_received", language=request.language_code, text_chars=len(request.text))
    try:
        with measure("tts_latency_ms"):
            audio, media_type = await tts.synthesize(request.text, request.speaker, request.language_code)
    except TextToSpeechError as exc:
        if metrics := current_metrics():
            metrics.record_error("tts")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    log_event("tts_completed", media_type=media_type, audio_bytes=len(audio))
    return Response(content=audio, media_type=media_type, headers={"Content-Disposition": "inline; filename=odia-ai.wav"})
