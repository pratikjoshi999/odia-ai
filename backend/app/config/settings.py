from functools import lru_cache
from pathlib import Path
import re

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    tagline: str
    prompt_file: str
    domain_terms: list[str]
    off_topic_reply: str
    off_topic_reply_en: str
    rag_data_dir: str
    rag_relevance_threshold: float = 0.25


class Settings(BaseSettings):
    app_env: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    agent_profile: str = "odisha"
    agent_config_dir: str = "backend/app/config/agents"
    agent: AgentProfile | None = None
    llm_provider: str = "local"
    llm_model: str = ""
    llm_timeout_seconds: float = 60.0
    llm_retry_attempts: int = 2
    llm_retry_base_delay_seconds: float = 1.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    sarvam_llm_base_url: str = "https://api.sarvam.ai"
    rag_top_k: int = 4
    embedding_model: str = "hashing-v1"
    stt_provider: str = "sarvam"
    stt_model: str = "saaras:v3"
    stt_language: str = "od-IN"
    stt_timeout_seconds: float = 30.0
    stt_max_audio_bytes: int = 10_000_000
    sarvam_api_key: str = ""
    tts_provider: str = "sarvam"
    tts_model: str = "bulbul:v3"
    tts_language: str = "od-IN"
    tts_speaker: str = "shubh"
    tts_timeout_seconds: float = 30.0
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings.model_copy(update={"agent": load_agent_profile(settings)})


def load_agent_profile(settings: Settings) -> AgentProfile:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", settings.agent_profile):
        raise ValueError("AGENT_PROFILE must contain only lowercase letters, numbers, '_' or '-'")

    project_root = Path(__file__).resolve().parents[3]
    config_dir = Path(settings.agent_config_dir)
    if not config_dir.is_absolute():
        config_dir = project_root / config_dir
    profile_path = config_dir / f"{settings.agent_profile}.yaml"
    try:
        raw_profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Agent profile not found: {profile_path}") from exc
    return AgentProfile.model_validate(raw_profile)
