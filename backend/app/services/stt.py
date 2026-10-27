from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config.settings import Settings


class SpeechToTextError(Exception):
    """Expected provider or input error safe to expose as a user-facing message."""


@dataclass(frozen=True)
class SpeechToTextResult:
    text: str
    language: str
    confidence: float | None = None


class SpeechToTextService(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, filename: str, content_type: str, language: str | None = None) -> SpeechToTextResult:
        raise NotImplementedError


class UnavailableSpeechToTextService(SpeechToTextService):
    async def transcribe(self, audio: bytes, filename: str, content_type: str, language: str | None = None) -> SpeechToTextResult:
        raise SpeechToTextError("ଭଏସ୍ ସେବା ବର୍ତ୍ତମାନ ସଂଯୋଗ ହୋଇନାହିଁ।")


class SarvamSpeechToTextService(SpeechToTextService):
    endpoint = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def transcribe(self, audio: bytes, filename: str, content_type: str, language: str | None = None) -> SpeechToTextResult:
        if not audio:
            raise SpeechToTextError("ଖାଲି ଅଡିଓ ପଠାଯାଇଛି।")
        files = {"file": (filename, audio, content_type or "application/octet-stream")}
        data = {
            "model": self.settings.stt_model,
            "language_code": language or self.settings.stt_language,
            "mode": "transcribe",
        }
        headers = {"api-subscription-key": self.settings.sarvam_api_key}
        try:
            async with httpx.AsyncClient(timeout=self.settings.stt_timeout_seconds) as client:
                response = await client.post(self.endpoint, headers=headers, data=data, files=files)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SpeechToTextError("ଭଏସ୍ ବୁଝିବାକୁ ଅଧିକ ସମୟ ଲାଗୁଛି। ପୁଣି ଚେଷ୍ଟା କରନ୍ତୁ।") from exc
        except httpx.HTTPStatusError as exc:
            raise SpeechToTextError("ଭଏସ୍ ସେବାରୁ ଉତ୍ତର ମିଳିଲା ନାହିଁ।") from exc
        except httpx.HTTPError as exc:
            raise SpeechToTextError("ଭଏସ୍ ସେବା ସହିତ ଯୋଗାଯୋଗ ହୋଇପାରିଲା ନାହିଁ।") from exc

        payload = response.json()
        text = str(payload.get("transcript", "")).strip()
        if not text:
            raise SpeechToTextError("ଅଡିଓରୁ କୌଣସି କଥା ବୁଝିହେଲା ନାହିଁ।")
        confidence = payload.get("confidence")
        return SpeechToTextResult(text=text, language=payload.get("language_code", language or self.settings.stt_language), confidence=confidence)


def get_stt_service(settings: Settings) -> SpeechToTextService:
    if settings.stt_provider.lower() == "sarvam" and settings.sarvam_api_key:
        return SarvamSpeechToTextService(settings)
    return UnavailableSpeechToTextService()
