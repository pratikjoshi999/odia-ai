from pydantic import BaseModel


class SpeechToTextResponse(BaseModel):
    text: str
    language: str
    confidence: float | None = None

