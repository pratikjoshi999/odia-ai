from typing import Literal

LanguageCode = Literal["od-IN", "en-IN"]


def detect_language(text: str) -> LanguageCode:
    """Detect Odia by Unicode script; otherwise use English for the MVP."""
    odia_characters = sum("\u0b00" <= character <= "\u0b7f" for character in text)
    return "od-IN" if odia_characters else "en-IN"


def language_instruction(language: LanguageCode) -> str:
    if language == "od-IN":
        return "Respond in natural Odia. Preserve Odisha place names, local terms, dates, and numbers."
    return "Respond in clear, natural English. Do not translate the answer into Odia unless the user asks for it."
