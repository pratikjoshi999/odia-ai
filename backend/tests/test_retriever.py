from pathlib import Path

from app.rag.retriever import load_chunks


def test_load_chunks_keeps_paragraphs_together(tmp_path: Path) -> None:
    knowledge_file = tmp_path / "local.txt"
    knowledge_file.write_text(
        "Topic: First\n\nNuapada is known as the Soup City of Odisha.\n\nTopic: Third",
        encoding="utf-8",
    )

    chunks = load_chunks(tmp_path, words_per_chunk=120)

    assert len(chunks) == 3
    assert chunks[1].text == "Nuapada is known as the Soup City of Odisha."


def test_long_paragraphs_are_still_split(tmp_path: Path) -> None:
    knowledge_file = tmp_path / "long.txt"
    knowledge_file.write_text(" ".join(["word"] * 125), encoding="utf-8")

    chunks = load_chunks(tmp_path, words_per_chunk=120)

    assert [len(chunk.text.split()) for chunk in chunks] == [120, 5]
