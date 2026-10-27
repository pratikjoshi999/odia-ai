from app.agents.conversation import OFF_TOPIC_REPLY_EN, classify_node, guard_node
from app.services.language import detect_language, language_instruction


def test_detects_odia_script() -> None:
    assert detect_language("ପୁରୀରେ କେଉଁଠି ବୁଲିବି?") == "od-IN"


def test_detects_english_text() -> None:
    assert detect_language("What are the best places to visit in Puri?") == "en-IN"


def test_classification_carries_language() -> None:
    state = classify_node({"message": "What are the best places to visit in Puri?"})
    assert state["language"] == "en-IN"
    assert guard_node({"language": "en-IN"})["reply"] == OFF_TOPIC_REPLY_EN


def test_language_instruction_is_explicit() -> None:
    assert "natural Odia" in language_instruction("od-IN")
    assert "natural English" in language_instruction("en-IN")
