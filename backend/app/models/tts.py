from pydantic import BaseModel, Field


class TextToSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    speaker: str | None = Field(default=None, max_length=50)
    language_code: str | None = Field(default=None, pattern=r"^(od-IN|en-IN)$")
