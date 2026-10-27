from app.config.settings import Settings
from app.services.llm import LocalLLMProvider, SarvamProvider, get_llm_provider


def test_sarvam_provider_is_selected_without_network_call() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="sarvam",
        sarvam_api_key="test-key",
        llm_model="sarvam-105b",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, SarvamProvider)


def test_sarvam_provider_falls_back_without_api_key() -> None:
    settings = Settings(_env_file=None, llm_provider="sarvam", sarvam_api_key="")

    provider = get_llm_provider(settings)

    assert isinstance(provider, LocalLLMProvider)
