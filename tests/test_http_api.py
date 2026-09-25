"""Acceptance tests for the local FastAPI adapter."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from src.adapters.http import create_app
from src.application.models import (
    AnswerCommand,
    IndexCommand,
    IndexOperationResult,
    RetrievalCommand,
)
from src.application.ports import TextGenerator
from src.application.use_cases import ABSTENTION_ANSWER, RagApplication
from src.domain import LexicalIndexMetadata, MinimalSource


def source() -> MinimalSource:
    """Build one exact HTTP response source."""
    return MinimalSource(
        file_path="data/raw/vllm-0.10.1/docs/api.md",
        first_character_index=0,
        last_character_index=4,
    )


class FakeGenerator:
    """Return deterministic HTTP answer text."""

    @property
    def supported_context_tokens(self) -> int:
        """Return enough room for the fixture prompt."""
        return 100

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Return one stable complete-template count."""
        del question, context
        return 10

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Return one grounded answer."""
        del question, context, max_new_tokens
        return "HTTP grounded answer."


class FakeOperations:
    """Fake every concrete operation behind the HTTP application."""

    def index(
        self,
        command: IndexCommand,
        show_progress: bool = False,
    ) -> IndexOperationResult:
        """Return structured index metadata without filesystem work."""
        assert show_progress is False
        return IndexOperationResult(
            operation="full",
            metadata=LexicalIndexMetadata(
                corpus_path=command.corpus_path,
                max_chunk_size=command.max_chunk_size,
                document_count=2,
                chunk_count=3,
            ),
            index_directory=command.save_directory,
        )

    def retrieve(
        self,
        command: RetrievalCommand,
        queries: list[str],
        batch: bool = False,
        show_progress: bool = False,
    ) -> list[list[MinimalSource]]:
        """Return exact sources or deliberate expected failures."""
        del command
        assert batch is False
        assert show_progress is False
        if queries == ["missing"]:
            raise FileNotFoundError("Lexical index not found")
        if queries == ["invalid"]:
            raise ValueError("invalid retrieval configuration")
        if queries == ["failed"]:
            raise RuntimeError("model failed")
        return [[source()] for _ in queries]

    def load_source_texts(
        self,
        index_directory: str,
        sources: Sequence[MinimalSource],
    ) -> list[str]:
        """Hydrate exact fake text."""
        del index_directory
        return ["text" for _ in sources]

    def make_generator(
        self,
        command: AnswerCommand,
        show_progress: bool = False,
    ) -> TextGenerator:
        """Return a quiet fake generator."""
        del command
        assert show_progress is False
        return FakeGenerator()


def client() -> TestClient:
    """Build the FastAPI factory around a fake application."""
    return TestClient(create_app(RagApplication(FakeOperations())))


def test_factory_includes_three_pipeline_routers_and_openapi() -> None:
    """The factory publishes only the approved pipeline operation family."""
    api = client()

    schema = api.get("/openapi.json")

    assert schema.status_code == 200
    document = schema.json()
    assert set(document["paths"]) == {"/index", "/search", "/answer"}
    expected_models = {
        "/index": ("IndexRequest", "IndexOperationResult"),
        "/search": ("SearchRequest", "MinimalSearchResults"),
        "/answer": ("AnswerRequest", "MinimalAnswer"),
    }
    for path, (request_model, response_model) in expected_models.items():
        operation = document["paths"][path]["post"]
        request_schema = operation["requestBody"]["content"][
            "application/json"
        ]["schema"]
        response_schema = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert request_schema["$ref"].endswith(request_model)
        assert response_schema["$ref"].endswith(response_model)
        for status in ("400", "404", "500"):
            error_schema = operation["responses"][status]["content"][
                "application/json"
            ]["schema"]
            assert error_schema["$ref"].endswith("ApiError")
    schemas = document["components"]["schemas"]
    assert schemas["IndexRequest"]["properties"]["max_chunk_size"][
        "default"
    ] == 2000
    assert schemas["SearchRequest"]["properties"]["k"]["default"] == 10
    assert schemas["AnswerRequest"]["properties"]["k"]["default"] == 10


def test_index_route_uses_shared_defaults_and_result_model() -> None:
    """Index validates through Pydantic and returns structured metadata."""
    response = client().post(
        "/index",
        json={"corpus_path": "corpus", "save_directory": "processed"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "operation": "full",
        "metadata": {
            "schema_version": 2,
            "retrieval_method": "sqlite-fts5-bm25",
            "corpus_path": "corpus",
            "max_chunk_size": 2000,
            "document_count": 2,
            "chunk_count": 3,
            "index_revision": 1,
        },
        "index_directory": "processed",
        "added_count": 0,
        "changed_count": 0,
        "deleted_count": 0,
        "semantic_action": None,
    }


def test_search_and_answer_routes_reuse_existing_output_models() -> None:
    """HTTP search and answer preserve exact source identity models."""
    api = client()

    search = api.post(
        "/search",
        json={"query": "question", "index_directory": "processed", "k": 1},
    )
    answer = api.post(
        "/answer",
        json={
            "query": "question",
            "index_directory": "processed",
            "k": 1,
            "token_budget": 100,
            "max_new_tokens": 10,
        },
    )

    assert search.status_code == answer.status_code == 200
    assert search.json()["question"] == "question"
    assert search.json()["retrieved_sources"] == [source().model_dump()]
    assert answer.json()["retrieved_sources"] == [source().model_dump()]
    assert answer.json()["answer"] == "HTTP grounded answer."


def test_expected_failures_return_json_without_tracebacks() -> None:
    """Known application failures map to stable local HTTP responses."""
    api = client()

    missing = api.post(
        "/search",
        json={"query": "missing", "index_directory": "processed"},
    )
    invalid = api.post(
        "/search",
        json={"query": "invalid", "index_directory": "processed"},
    )
    failed = api.post(
        "/search",
        json={"query": "failed", "index_directory": "processed"},
    )
    malformed = api.post("/search", json={"index_directory": "processed"})

    assert missing.status_code == 404
    assert missing.json() == {"error": "Lexical index not found"}
    assert invalid.status_code == 400
    assert invalid.json() == {"error": "invalid retrieval configuration"}
    assert failed.status_code == 500
    assert failed.json() == {"error": "model failed"}
    assert malformed.status_code == 422
    assert "traceback" not in failed.text.lower()


def test_real_tiny_index_search_and_model_free_answer(tmp_path: Path) -> None:
    """Serve all real routes without model assets at k zero."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    document = corpus / "guide.md"
    document.write_text("needle documentation\n", encoding="utf-8")
    processed = tmp_path / "processed"
    api = TestClient(create_app())

    indexed = api.post(
        "/index",
        json={
            "corpus_path": str(corpus),
            "save_directory": str(processed),
        },
    )
    searched = api.post(
        "/search",
        json={
            "query": "needle",
            "index_directory": str(processed),
            "k": 1,
        },
    )
    answered = api.post(
        "/answer",
        json={
            "query": "needle",
            "index_directory": str(processed),
            "k": 0,
            "local_files_only": True,
        },
    )

    assert indexed.status_code == 200
    assert indexed.json()["metadata"]["document_count"] == 1
    assert searched.status_code == 200
    assert len(searched.json()["retrieved_sources"]) == 1
    assert answered.status_code == 200
    assert answered.json()["answer"] == ABSTENTION_ANSWER
    assert answered.json()["retrieved_sources"] == []
