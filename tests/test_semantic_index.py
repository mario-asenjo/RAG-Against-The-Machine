"""Acceptance tests for optional semantic embedding retrieval."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

import pytest
import torch
import fire

from src.adapters.cli import RagCli
from src.domain import (
    IndexedFile,
    LexicalIndexBuild,
    LexicalIndexMetadata,
    LexicalIndexUpdate,
    SourceChunk,
    StudentSearchResults,
)
from src.infrastructure import load_index_metadata, save_lexical_index
from src.infrastructure.semantic import (
    SEMANTIC_INDEX_FILENAME,
    MiniLmEmbedder,
    build_semantic_index,
    ensure_semantic_index,
    load_semantic_index,
    search_semantic_index,
    update_semantic_index,
)


class FakeEmbedder:
    """Return deterministic normalized vectors and record embedded texts."""

    def __init__(self, model_name: str = "fake/model") -> None:
        """Set one artifact-compatible fake model signature."""
        self.model_name = model_name
        self.model_revision = "revision-1"
        self.max_length = 256
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> torch.Tensor:
        """Map needle text to one axis and other text to another."""
        self.calls.append(list(texts))
        vectors = [
            [1.0, 0.0] if "needle" in text else [0.0, 1.0]
            for text in texts
        ]
        return torch.tensor(vectors, dtype=torch.float32).reshape(
            len(texts), 2
        )


def chunk(path: str, start: int, text: str) -> SourceChunk:
    """Create one exact text chunk with a concise identity."""
    return SourceChunk(
        file_path=path,
        first_character_index=start,
        last_character_index=start + len(text),
        chunk_type="text",
        text=text,
    )


def lexical_build(
    chunks: list[SourceChunk],
    revision: int = 1,
) -> LexicalIndexBuild:
    """Build canonical SQLite input for semantic-search tests."""
    paths = sorted({item.file_path for item in chunks})
    return LexicalIndexBuild(
        metadata=LexicalIndexMetadata(
            corpus_path="corpus",
            max_chunk_size=2000,
            document_count=len(paths),
            chunk_count=len(chunks),
            index_revision=revision,
        ),
        chunks=chunks,
        files=[
            IndexedFile(
                file_path=path,
                content_hash="0" * 64,
                byte_count=max(
                    item.last_character_index
                    for item in chunks
                    if item.file_path == path
                ),
                character_count=max(
                    item.last_character_index
                    for item in chunks
                    if item.file_path == path
                ),
            )
            for path in paths
        ],
    )


def test_full_semantic_build_matches_canonical_chunks(tmp_path: Path) -> None:
    """The artifact stores normalized float32 rows in exact canonical order."""
    chunks = [
        chunk("corpus/a.md", 3, "ordinary"),
        chunk("corpus/b.py", 10, "needle implementation"),
    ]
    embedder = FakeEmbedder()
    path = tmp_path / SEMANTIC_INDEX_FILENAME

    build_semantic_index(chunks, path, 7, embedder)
    metadata, embeddings, sources = load_semantic_index(
        path,
        expected_source_index_revision=7,
        expected_model_name=embedder.model_name,
        expected_model_revision=embedder.model_revision,
        expected_max_length=embedder.max_length,
        canonical_chunks=chunks,
    )

    assert metadata.schema_version == 1
    assert metadata.embedding_dimension == 2
    assert metadata.chunk_count == len(chunks) == len(sources)
    assert metadata.source_index_revision == 7
    assert embeddings.dtype == torch.float32
    assert torch.allclose(
        torch.linalg.vector_norm(embeddings, dim=1),
        torch.ones(2),
    )
    assert [source.model_dump() for source in sources] == [
        {
            "file_path": item.file_path,
            "first_character_index": item.first_character_index,
            "last_character_index": item.last_character_index,
        }
        for item in chunks
    ]
    assert embedder.calls == [[item.text for item in chunks]]


def test_semantic_noop_keeps_artifact_bytes_and_skips_embedding(
    tmp_path: Path,
) -> None:
    """A valid same-revision artifact is a true semantic no-op."""
    chunks = [chunk("corpus/a.md", 0, "needle")]
    embedder = FakeEmbedder()
    path = tmp_path / SEMANTIC_INDEX_FILENAME
    build_semantic_index(chunks, path, 1, embedder)
    before = path.read_bytes()
    embedder.calls.clear()

    rebuilt = ensure_semantic_index(chunks, path, 1, embedder)

    assert rebuilt is False
    assert path.read_bytes() == before
    assert embedder.calls == []


@pytest.mark.parametrize("state", ["missing", "stale", "incompatible"])
def test_missing_stale_or_incompatible_semantic_index_rebuilds_only_semantic(
    tmp_path: Path,
    state: str,
) -> None:
    """Invalid semantic state is replaced from supplied canonical chunks."""
    chunks = [chunk("corpus/a.md", 0, "needle")]
    path = tmp_path / SEMANTIC_INDEX_FILENAME
    original = FakeEmbedder()
    if state != "missing":
        build_semantic_index(chunks, path, 1, original)
    embedder = FakeEmbedder(
        "fake/replacement" if state == "incompatible" else original.model_name
    )
    expected_revision = 2 if state == "stale" else 1
    embedder.calls.clear()

    rebuilt = ensure_semantic_index(
        chunks,
        path,
        expected_revision,
        embedder,
    )

    assert rebuilt is True
    metadata, _, _ = load_semantic_index(
        path,
        expected_source_index_revision=expected_revision,
        expected_model_name=embedder.model_name,
        expected_model_revision=embedder.model_revision,
        expected_max_length=embedder.max_length,
        canonical_chunks=chunks,
    )
    assert metadata.source_index_revision == expected_revision
    assert embedder.calls == [["needle"]]


def test_incremental_semantic_update_invalidates_whole_changed_files(
    tmp_path: Path,
) -> None:
    """Only unchanged-file rows are reused, regardless of matching offsets."""
    previous = [
        chunk("corpus/a.md", 0, "unchanged"),
        chunk("corpus/b.md", 0, "old first"),
        chunk("corpus/b.md", 20, "old second"),
        chunk("corpus/deleted.md", 0, "deleted"),
    ]
    changed_chunks = [
        chunk("corpus/b.md", 0, "new first"),
        chunk("corpus/b.md", 20, "new second"),
        chunk("corpus/renamed.md", 0, "needle renamed"),
    ]
    final = [previous[0], *changed_chunks]
    embedder = FakeEmbedder()
    path = tmp_path / SEMANTIC_INDEX_FILENAME
    build_semantic_index(previous, path, 1, embedder)
    _, old_embeddings, _ = load_semantic_index(path)
    embedder.calls.clear()
    update = LexicalIndexUpdate(
        metadata=LexicalIndexMetadata(
            corpus_path="corpus",
            max_chunk_size=2000,
            document_count=3,
            chunk_count=len(final),
            index_revision=2,
        ),
        files=[
            IndexedFile(
                file_path=name,
                content_hash="1" * 64,
                byte_count=100,
                character_count=100,
            )
            for name in ("corpus/a.md", "corpus/b.md", "corpus/renamed.md")
        ],
        changed_paths=["corpus/b.md", "corpus/renamed.md"],
        removed_paths=["corpus/deleted.md"],
        changed_chunks=changed_chunks,
        reused_file_count=1,
    )

    update_semantic_index(path, previous, final, update, embedder)

    metadata, embeddings, sources = load_semantic_index(
        path,
        expected_source_index_revision=2,
        canonical_chunks=final,
    )
    assert metadata.chunk_count == len(final)
    assert [source.file_path for source in sources] == [
        item.file_path for item in final
    ]
    assert torch.equal(embeddings[0], old_embeddings[0])
    assert embedder.calls == [[item.text for item in changed_chunks]]


def test_semantic_persistence_failure_preserves_previous_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed temporary write must not replace the last valid artifact."""
    chunks = [chunk("corpus/a.md", 0, "needle")]
    path = tmp_path / SEMANTIC_INDEX_FILENAME
    embedder = FakeEmbedder()
    build_semantic_index(chunks, path, 1, embedder)
    before = path.read_bytes()

    def fail_save(*args: object, **kwargs: object) -> None:
        raise RuntimeError("disk failure")

    monkeypatch.setattr(torch, "save", fail_save)

    with pytest.raises(RuntimeError, match="Could not persist semantic index"):
        build_semantic_index(chunks, path, 2, embedder)

    assert path.read_bytes() == before
    assert not path.with_name(f".{path.name}.tmp").exists()


def test_semantic_search_rejects_stale_revision_before_embedding(
    tmp_path: Path,
) -> None:
    """Search rejects a projection from another SQLite revision."""
    chunks = [chunk("corpus/a.md", 0, "needle")]
    lexical_path = save_lexical_index(
        lexical_build(chunks, revision=2),
        tmp_path / "lexical_index.sqlite3",
    )
    semantic_path = tmp_path / SEMANTIC_INDEX_FILENAME
    embedder = FakeEmbedder()
    build_semantic_index(chunks, semantic_path, 1, embedder)
    embedder.calls.clear()

    with pytest.raises(ValueError, match="source_index_revision"):
        search_semantic_index(
            semantic_path,
            lexical_path,
            "needle query",
            1,
            embedder,
        )

    assert embedder.calls == []


def test_semantic_search_returns_exact_paths_offsets_and_topk(
    tmp_path: Path,
) -> None:
    """Cosine top-k projects unchanged canonical source identities."""
    chunks = [
        chunk("corpus/a.md", 11, "ordinary"),
        chunk("corpus/b.py", 101, "needle implementation"),
    ]
    lexical_path = save_lexical_index(
        lexical_build(chunks),
        tmp_path / "lexical_index.sqlite3",
    )
    semantic_path = tmp_path / SEMANTIC_INDEX_FILENAME
    embedder = FakeEmbedder()
    build_semantic_index(chunks, semantic_path, 1, embedder)

    results = search_semantic_index(
        semantic_path,
        lexical_path,
        "needle question",
        1,
        embedder,
    )

    assert [result.model_dump() for result in results] == [
        {
            "file_path": "corpus/b.py",
            "first_character_index": 101,
            "last_character_index": 122,
        }
    ]
    width = (
        results[0].last_character_index
        - results[0].first_character_index
    )
    assert width <= 2000


def test_semantic_topk_breaks_equal_scores_by_canonical_order(
    tmp_path: Path,
) -> None:
    """Equal cosine scores retain the canonical SQLite chunk order."""
    chunks = [
        chunk(f"corpus/{name}.md", 0, "ordinary")
        for name in ("a", "b", "c")
    ]
    lexical_path = save_lexical_index(
        lexical_build(chunks),
        tmp_path / "lexical_index.sqlite3",
    )
    semantic_path = tmp_path / SEMANTIC_INDEX_FILENAME
    embedder = FakeEmbedder()
    build_semantic_index(chunks, semantic_path, 1, embedder)

    results = search_semantic_index(
        semantic_path,
        lexical_path,
        "ordinary query",
        2,
        embedder,
    )

    assert [result.file_path for result in results] == [
        "corpus/a.md",
        "corpus/b.md",
    ]


def test_minilm_uses_attention_masked_mean_pooling_and_l2_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The raw Transformers adapter reproduces MiniLM sentence pooling."""
    import transformers

    class Tokenizer:
        def __call__(
            self,
            texts: Sequence[str],
            **kwargs: object,
        ) -> dict[str, torch.Tensor]:
            assert list(texts) == ["one", "two"]
            assert kwargs["padding"] is True
            assert kwargs["truncation"] is True
            assert kwargs["max_length"] == 256
            return {
                "input_ids": torch.tensor([[1, 2], [3, 4]]),
                "attention_mask": torch.tensor([[1, 0], [1, 1]]),
            }

    class Model:
        config = SimpleNamespace(hidden_size=2)

        def eval(self) -> "Model":
            return self

        def __call__(self, **inputs: torch.Tensor) -> SimpleNamespace:
            assert "attention_mask" in inputs
            return SimpleNamespace(
                last_hidden_state=torch.tensor(
                    [
                        [[2.0, 0.0], [100.0, 0.0]],
                        [[0.0, 2.0], [0.0, 4.0]],
                    ]
                )
            )

    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: Tokenizer(),
    )
    monkeypatch.setattr(
        transformers.AutoModel,
        "from_pretrained",
        lambda *args, **kwargs: Model(),
    )
    embedder = MiniLmEmbedder(cache_directory=tmp_path, local_files_only=True)

    embeddings = embedder.encode(["one", "two"])

    assert embeddings.dtype == torch.float32
    assert torch.allclose(
        embeddings,
        torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
    )


def test_index_semantic_flag_builds_from_the_saved_canonical_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index adds semantic without changing lexical chunks."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "a.md"
    source.write_text("needle documentation\n", encoding="utf-8")
    output = tmp_path / "processed"
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )

    message = RagCli().index(
        corpus_path=str(corpus),
        save_directory=str(output),
        semantic=True,
        local_files_only=True,
    )

    assert "semantic" in message.lower()
    metadata, _, sources = load_semantic_index(
        output / SEMANTIC_INDEX_FILENAME,
        expected_source_index_revision=1,
    )
    assert metadata.chunk_count == len(sources) == 1
    assert sources[0].file_path == source.as_posix()


def test_semantic_search_cli_and_dataset_preserve_output_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both public search boundaries select semantic ranking explicitly."""
    chunks = [
        chunk("corpus/a.md", 4, "ordinary"),
        chunk("corpus/b.py", 20, "needle implementation"),
    ]
    lexical_path = save_lexical_index(
        lexical_build(chunks),
        tmp_path / "lexical_index.sqlite3",
    )
    embedder = FakeEmbedder()
    build_semantic_index(
        chunks,
        tmp_path / SEMANTIC_INDEX_FILENAME,
        1,
        embedder,
    )
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )
    cli = RagCli()

    single = cli.search(
        "needle question",
        k=1,
        index_directory=str(lexical_path.parent),
        semantic=True,
    )
    assert single == "corpus/b.py [20:41]"

    dataset_path = tmp_path / "questions.json"
    dataset_path.write_text(
        "{\"rag_questions\":["
        "{\"question_id\":\"q1\",\"question\":\"needle question\"},"
        "{\"question_id\":\"q2\",\"question\":\"ordinary query\"}]}\n",
        encoding="utf-8",
    )
    output_directory = tmp_path / "results"
    cli.search_dataset(
        dataset_path=str(dataset_path),
        k=1,
        save_directory=str(output_directory),
        index_directory=str(lexical_path.parent),
        semantic=True,
    )
    output = StudentSearchResults.model_validate_json(
        (output_directory / dataset_path.name).read_text(encoding="utf-8")
    )
    assert output.k == 1
    assert [item.question_id for item in output.search_results] == ["q1", "q2"]
    assert [
        item.retrieved_sources[0].file_path for item in output.search_results
    ] == ["corpus/b.py", "corpus/a.md"]


def test_incremental_semantic_cli_advances_to_sqlite_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful changed-file update leaves both projections current."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "a.md"
    source.write_text("before\n", encoding="utf-8")
    output = tmp_path / "processed"
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )
    cli = RagCli()
    cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        semantic=True,
    )
    embedder.calls.clear()
    source.write_text("needle after\n", encoding="utf-8")

    message = cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        incremental=True,
        semantic=True,
    )

    lexical_revision = load_index_metadata(
        output / "lexical_index.sqlite3"
    ).index_revision
    semantic_metadata, _, _ = load_semantic_index(
        output / SEMANTIC_INDEX_FILENAME
    )
    assert "semantic index updated" in message.lower()
    assert semantic_metadata.source_index_revision == lexical_revision == 2
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 1
    assert "needle after" in embedder.calls[0][0]


def test_lexical_fallback_removes_projection_when_revision_resets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full lexical fallback cannot leave a same-number stale projection."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "a.md"
    source.write_text("before\n", encoding="utf-8")
    output = tmp_path / "processed"
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )
    cli = RagCli()
    cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        semantic=True,
    )
    lexical_path = output / "lexical_index.sqlite3"
    semantic_path = output / SEMANTIC_INDEX_FILENAME
    source.write_text("changed", encoding="utf-8")
    connection = sqlite3.connect(lexical_path)
    try:
        connection.execute(
            "UPDATE metadata SET payload = 'invalid' WHERE id = 1"
        )
        connection.commit()
    finally:
        connection.close()

    message = cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        incremental=True,
    )

    assert "full rebuild fallback" in message.lower()
    assert load_index_metadata(lexical_path).index_revision == 1
    assert not semantic_path.exists()


def test_semantic_rebuild_on_lexical_noop_does_not_replace_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing projection rebuild leaves the canonical no-op byte-stable."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_text("needle\n", encoding="utf-8")
    output = tmp_path / "processed"
    cli = RagCli()
    cli.index(corpus_path=str(corpus), save_directory=str(output))
    lexical_path = output / "lexical_index.sqlite3"
    before = lexical_path.read_bytes()
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )

    message = cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        incremental=True,
        semantic=True,
    )

    assert "index unchanged" in message.lower()
    assert "semantic index rebuilt" in message.lower()
    assert lexical_path.read_bytes() == before
    assert load_index_metadata(lexical_path).index_revision == 1


@pytest.mark.parametrize("corrupt_lexical_metadata", [False, True])
def test_semantic_failure_leaves_detectable_stale_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corrupt_lexical_metadata: bool,
) -> None:
    """SQLite may advance while the prior atomic semantic artifact survives."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "a.md"
    source.write_text("before\n", encoding="utf-8")
    output = tmp_path / "processed"
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "src.infrastructure.pipeline.MiniLmEmbedder",
        lambda **kwargs: embedder,
    )
    cli = RagCli()
    cli.index(
        corpus_path=str(corpus),
        save_directory=str(output),
        semantic=True,
    )
    semantic_path = output / SEMANTIC_INDEX_FILENAME
    before = semantic_path.read_bytes()
    source.write_text("needle after\n", encoding="utf-8")
    lexical_path = output / "lexical_index.sqlite3"
    if corrupt_lexical_metadata:
        connection = sqlite3.connect(lexical_path)
        try:
            connection.execute(
                "UPDATE metadata SET payload = 'invalid' WHERE id = 1"
            )
            connection.commit()
        finally:
            connection.close()
    real_replace = Path.replace

    def fail_semantic_replace(source_path: Path, target: Path) -> Path:
        if source_path.name == f".{SEMANTIC_INDEX_FILENAME}.tmp":
            raise OSError("semantic replacement failed")
        return real_replace(source_path, target)

    monkeypatch.setattr(Path, "replace", fail_semantic_replace)

    with pytest.raises(
        fire.core.FireError,
        match="semantic replacement failed",
    ):
        cli.index(
            corpus_path=str(corpus),
            save_directory=str(output),
            incremental=True,
            semantic=True,
        )

    assert load_index_metadata(lexical_path).index_revision == 2
    assert semantic_path.read_bytes() == before
    semantic_metadata, _, _ = load_semantic_index(semantic_path)
    assert semantic_metadata.source_index_revision == 1
