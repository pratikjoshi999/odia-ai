from abc import ABC, abstractmethod
import asyncio
from collections.abc import Sequence
from pathlib import Path
import random

import httpx

from app.config.settings import Settings
from app.models.chat import ConversationMessage
from app.services.language import LanguageCode, language_instruction
from app.utils.observability import log_event


SYSTEM_PROMPT = """You are a helpful conversational assistant.
Follow the agent instructions below as the source of truth for your role, domain,
tone, and safety boundaries. Preserve names, local terminology, dates, and numbers.
Do not invent facts or claim capabilities that are not available."""


def load_agent_prompt(settings: Settings) -> str:
    project_root = Path(__file__).resolve().parents[3]
    if settings.agent is None:
        return ""
    prompt_path = Path(settings.agent.prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = project_root / prompt_path
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_system_prompt(settings: Settings, language: LanguageCode, context: str = "") -> str:
    prompt = SYSTEM_PROMPT
    agent_prompt = load_agent_prompt(settings)
    if agent_prompt:
        prompt += f"\n\nAgent instructions:\n{agent_prompt}"
    prompt += "\n\n" + language_instruction(language)
    if context:
        prompt += f"\n\nUse this knowledge context when relevant:\n{context}"
    return prompt


class LLMProvider(ABC):
    name = "unknown"

    @abstractmethod
    async def generate(self, message: str, history: Sequence[ConversationMessage] = (), context: str = "", language: LanguageCode = "od-IN") -> str:
        raise NotImplementedError


class LocalLLMProvider(LLMProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, message: str, history: Sequence[ConversationMessage] = (), context: str = "", language: LanguageCode = "od-IN") -> str:
        if context:
            if language == "en-IN":
                return f"{context}\n\nThis answer is based on the Odisha information above."
            return f"{context}\n\nଏହି ସୂଚନା ଆଧାରରେ ଆପଣଙ୍କ ପ୍ରଶ୍ନର ଉତ୍ତର ଦିଆଯାଇଛି।"
        return (
            "Hello! I am an assistant for Odisha-related information. "
            "A language model is not connected yet. Please configure an LLM provider."
            if language == "en-IN" else
            "ନମସ୍କାର! ମୁଁ ଓଡ଼ିଶା ସମ୍ବନ୍ଧୀୟ ସୂଚନା ପାଇଁ ଆପଣଙ୍କ ସହାୟକ। "
            "ଆପଣଙ୍କ ପ୍ରଶ୍ନର ଉତ୍ତର ପାଇଁ ମଡେଲ୍ ସଂଯୋଗ କରାଯାଇନାହିଁ। "
            "ଦୟାକରି OPENAI_API_KEY କିମ୍ବା GEMINI_API_KEY ସେଟ୍ କରନ୍ତୁ।"
        )


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, message: str, history: Sequence[ConversationMessage] = (), context: str = "", language: LanguageCode = "od-IN") -> str:
        system_prompt = build_system_prompt(self.settings, language, context)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.text} for item in history[-10:])
        messages.append({"role": "user", "content": message})
        headers = {"Authorization": f"Bearer {self.settings.ollama_api_key}"} if self.settings.ollama_api_key else {}
        payload = {"model": self.settings.llm_model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self.settings.llm_timeout_seconds,
            ) as client:
                response = await client.post("/api/chat", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Ollama is unavailable") from exc
        return response.json()["message"]["content"]


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, message: str, history: Sequence[ConversationMessage] = (), context: str = "", language: LanguageCode = "od-IN") -> str:
        system_prompt = build_system_prompt(self.settings, language, context)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.text} for item in history[-10:])
        messages.append({"role": "user", "content": message})
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
        }
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, message: str, history: Sequence[ConversationMessage] = (), context: str = "", language: LanguageCode = "od-IN") -> str:
        model = self.settings.llm_model or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        contents = [{"role": "user" if item.role == "user" else "model", "parts": [{"text": item.text}]} for item in history[-10:]]
        contents.append({"role": "user", "parts": [{"text": message}]})
        system_prompt = build_system_prompt(self.settings, language, context)
        payload = {"system_instruction": {"parts": [{"text": system_prompt}]}, "contents": contents}
        headers = {
            "x-goog-api-key": self.settings.gemini_api_key,
            "Content-Type": "application/json",
        }
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            for attempt in range(self.settings.llm_retry_attempts + 1):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    is_last_attempt = attempt >= self.settings.llm_retry_attempts
                    if status_code not in retryable_statuses or is_last_attempt:
                        raise
                    delay = self.settings.llm_retry_base_delay_seconds * (2**attempt)
                    delay += random.uniform(0, self.settings.llm_retry_base_delay_seconds * 0.25)
                    log_event(
                        "llm_retry_scheduled",
                        provider=self.name,
                        status_code=status_code,
                        attempt=attempt + 1,
                        delay_ms=round(delay * 1000, 2),
                    )
                    await asyncio.sleep(delay)
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


class SarvamProvider(LLMProvider):
    """Sarvam Chat Completion adapter."""

    name = "sarvam"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self,
        message: str,
        history: Sequence[ConversationMessage] = (),
        context: str = "",
        language: LanguageCode = "od-IN",
    ) -> str:
        system_prompt = build_system_prompt(self.settings, language, context)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.text} for item in history[-10:])
        messages.append({"role": "user", "content": message})
        payload = {
            "model": self.settings.llm_model or "sarvam-m",
            "messages": messages,
        }
        headers = {
            "api-subscription-key": self.settings.sarvam_api_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.sarvam_llm_base_url,
                timeout=self.settings.llm_timeout_seconds,
            ) as client:
                response = await client.post("/v1/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Sarvam LLM is unavailable") from exc

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Sarvam returned an invalid response") from exc


def get_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "ollama" and settings.llm_model:
        return OllamaProvider(settings)
    if provider == "openai" and settings.openai_api_key and settings.llm_model:
        return OpenAIProvider(settings)
    if provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings)
    if provider == "sarvam" and settings.sarvam_api_key:
        return SarvamProvider(settings)
    return LocalLLMProvider(settings)
