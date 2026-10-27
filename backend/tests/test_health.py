from fastapi.testclient import TestClient

from app.main import app
from app.rag.service import get_rag_service


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_uses_local_fallback() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "ନମସ୍କାର"})
    assert response.status_code == 200
    assert response.json()["provider"] == "local"


def test_chat_blocks_off_topic_questions() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "Who won yesterday's football match?"})
    assert response.status_code == 200
    assert response.json()["provider"] == "policy"
    assert "ଓଡ଼ିଶା" in response.json()["reply"]


def test_chat_accepts_conversation_history() -> None:
    response = TestClient(app).post(
        "/api/chat",
        json={"message": "ପୁରୀ ବିଷୟରେ କହନ୍ତୁ", "history": [{"role": "user", "text": "ନମସ୍କାର"}]},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "local"


def test_rag_retrieves_puri_content() -> None:
    context = get_rag_service().retrieve("ପୁରୀ ଶ୍ରୀଜଗନ୍ନାଥ ମନ୍ଦିର")
    assert "ପୁରୀ" in context
    assert "ଜଗନ୍ନାଥ" in context


def test_chat_includes_retrieved_context() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "ପୁରୀରେ କେଉଁଠି ବୁଲିବି?"})
    assert response.status_code == 200
    assert response.json()["provider"] == "local"
    assert "ପୁରୀ" in response.json()["reply"]


def test_stt_rejects_unsupported_audio() -> None:
    response = TestClient(app).post("/api/stt", files={"audio": ("note.txt", b"not audio", "text/plain")})
    assert response.status_code == 400


def test_stt_rejects_empty_audio() -> None:
    response = TestClient(app).post("/api/stt", files={"audio": ("recording.webm", b"", "audio/webm")})
    assert response.status_code == 400


def test_tts_requires_provider_without_spending_credits() -> None:
    response = TestClient(app).post("/api/tts", json={"text": "ନମସ୍କାର", "speaker": "shubh"})
    assert response.status_code == 502


def test_request_id_is_returned_and_propagated() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-ID": "phase-seven-test"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase-seven-test"
