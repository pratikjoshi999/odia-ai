from abc import ABC, abstractmethod
import base64

import httpx

from app.config.settings import Settings


class TextToSpeechError(Exception):
    """Expected TTS error safe to expose to the client."""


class TextToSpeechService(ABC):
    @abstractmethod
    async def synthesize(self, text: str, speaker: str | None = None, language: str | None = None) -> tuple[bytes, str]:
        raise NotImplementedError


class UnavailableTextToSpeechService(TextToSpeechService):
    async def synthesize(self, text: str, speaker: str | None = None, language: str | None = None) -> tuple[bytes, str]:
        raise TextToSpeechError("ଭଏସ୍ ଆଉଟପୁଟ୍ ବର୍ତ୍ତମାନ ସଂଯୋଗ ହୋଇନାହିଁ।")


class SarvamTextToSpeechService(TextToSpeechService):
    endpoint = "https://api.sarvam.ai/text-to-speech"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def synthesize(self, text: str, speaker: str | None = None, language: str | None = None) -> tuple[bytes, str]:
        if not text.strip():
            raise TextToSpeechError("ଖାଲି ଟେକ୍ସଟ୍ ପାଇଁ ଭଏସ୍ ତିଆରି କରିହେବ ନାହିଁ।")
        payload = {
            "text": text.strip(),
            "language_code": language or self.settings.tts_language,
            "model": self.settings.tts_model,
            # Sarvam speaker IDs are case-sensitive and must be lowercase.
            "speaker": (speaker or self.settings.tts_speaker).strip().lower(),
            "output_audio_codec": "wav",
            "speech_sample_rate": 24000,
        }
        headers = {"api-subscription-key": self.settings.sarvam_api_key}
        try:
            async with httpx.AsyncClient(timeout=self.settings.tts_timeout_seconds) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TextToSpeechError("ଭଏସ୍ ତିଆରି କରିବାକୁ ଅଧିକ ସମୟ ଲାଗୁଛି।") from exc
        except httpx.HTTPError as exc:
            raise TextToSpeechError("ଭଏସ୍ ସେବାରୁ ଅଡିଓ ମିଳିଲା ନାହିଁ।") from exc
        try:
            audio = base64.b64decode(response.json()["audios"][0], validate=True)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise TextToSpeechError("ଭଏସ୍ ସେବାରୁ ଅବୈଧ ଅଡିଓ ମିଳିଲା।") from exc
        if not audio:
            raise TextToSpeechError("ଭଏସ୍ ସେବାରୁ ଖାଲି ଅଡିଓ ମିଳିଲା।")
        return audio, "audio/wav"


def get_tts_service(settings: Settings) -> TextToSpeechService:
    if settings.tts_provider.lower() == "sarvam" and settings.sarvam_api_key:
        return SarvamTextToSpeechService(settings)
    return UnavailableTextToSpeechService()
