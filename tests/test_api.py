"""HTTP surface tests: validation, auth failures, rate limiting, caching, SSE."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from argus import api as api_module
from argus.api import app


@pytest.fixture
def client(monkeypatch, fake_llm, fake_search, fake_fetch) -> TestClient:
    monkeypatch.setattr(api_module, "get_llm", lambda *_a, **_k: fake_llm)
    api_module.cache._store.clear()
    api_module.limiter._hits.clear()
    return TestClient(app)


def test_health_reports_readiness(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["status"] == "online"
    assert "version" in body
    assert isinstance(body["models_ready"], list)


def test_model_catalogue_never_exposes_keys(client: TestClient) -> None:
    body = client.get("/api/models").json()
    assert body["default"] == "groq-gpt-oss-120b"
    assert body["models"], "catalogue must not be empty"
    serialised = json.dumps(body)
    assert "gsk_" not in serialised and "api_key" not in serialised
    for model in body["models"]:
        assert set(model) >= {"id", "label", "provider", "ready"}


@pytest.mark.parametrize(
    "topic",
    ["", "  ", "ab", "x" * 5000],
    ids=["empty", "whitespace", "too-short", "too-long"],
)
def test_topic_validation_rejects_bad_input(client: TestClient, topic: str) -> None:
    resp = client.post("/api/research", json={"topic": topic})
    assert resp.status_code == 422


def test_topic_whitespace_is_normalised(client: TestClient) -> None:
    resp = client.post("/api/research", json={"topic": "  rare   earth\n minerals  "})
    assert resp.status_code == 200
    assert resp.json()["topic"] == "rare earth minerals"


def test_unknown_model_is_a_client_error(client: TestClient, monkeypatch) -> None:
    from argus.llm import ModelNotFoundError

    def boom(*_a, **_k):
        raise ModelNotFoundError("Unknown model 'gpt-9'.")

    monkeypatch.setattr(api_module, "get_llm", boom)
    resp = client.post("/api/research", json={"topic": "a valid topic", "model": "gpt-9"})
    assert resp.status_code == 400


def test_missing_credentials_returns_402(client: TestClient, monkeypatch) -> None:
    from argus.llm import MissingCredentialsError

    def boom(*_a, **_k):
        raise MissingCredentialsError("No API key available for Gemini 2.0 Flash.")

    monkeypatch.setattr(api_module, "get_llm", boom)
    resp = client.post("/api/research", json={"topic": "a valid topic"})
    assert resp.status_code == 402
    assert "API key" in resp.json()["detail"]


def test_research_returns_a_complete_payload(client: TestClient) -> None:
    body = client.post("/api/research", json={"topic": "rare earth minerals"}).json()
    assert body["report"]
    assert body["scores"]["overall"] == 7.5
    assert len(body["followup_questions"]) == 5
    assert body["sources"]
    assert body["cached"] is False


def test_identical_requests_are_served_from_cache(client: TestClient) -> None:
    payload = {"topic": "cache me please"}
    assert client.post("/api/research", json=payload).json()["cached"] is False
    assert client.post("/api/research", json=payload).json()["cached"] is True


def test_caller_supplied_keys_are_never_cached(client: TestClient) -> None:
    """A user's own key must not populate a cache other users can read from."""
    payload = {"topic": "private research", "api_key": "sk-user-key"}
    client.post("/api/research", json=payload)
    fresh = client.post("/api/research", json={"topic": "private research"})
    assert fresh.json()["cached"] is False


def test_rate_limit_returns_429_with_retry_after(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(api_module.limiter, "limit", 2)
    statuses = [
        client.post("/api/research", json={"topic": f"topic number {i}"}).status_code
        for i in range(4)
    ]
    assert statuses[:2] == [200, 200]
    assert 429 in statuses[2:]
    blocked = client.post("/api/research", json={"topic": "another one"})
    assert "Retry-After" in blocked.headers


def test_legacy_endpoint_keeps_its_old_field_names(client: TestClient) -> None:
    body = client.post(
        "/research", json={"topic": "legacy client", "model": "Groq — Llama 3.3 70B"}
    ).json()
    assert "feedback" in body and "followup_questions" in body
    assert body["report"]


def test_stream_emits_sse_events_in_order(client: TestClient) -> None:
    with client.stream("POST", "/api/research/stream", json={"topic": "streaming test"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [
            line[len("event: ") :].strip()
            for line in resp.iter_lines()
            if line.startswith("event: ")
        ]

    assert events[0] == "open"
    assert events[1] == "run_started"
    assert events[-1] == "run_completed"
    assert "token" in events
    assert events.count("stage_started") == events.count("stage_completed")


def test_stream_payload_carries_parsed_scores(client: TestClient) -> None:
    with client.stream("POST", "/api/research/stream", json={"topic": "score parsing"}) as resp:
        payloads = [
            json.loads(line[len("data: ") :])
            for line in resp.iter_lines()
            if line.startswith("data: ")
        ]

    critic = next(p for p in payloads if p.get("stage") == "critic" and "scores" in p)
    assert critic["scores"]["overall"] == 7.5
    final = payloads[-1]["result"]
    assert final["scores"]["categories"]["Use of Sources"] == 6.0


def test_stream_replays_a_cached_run_without_calling_the_model(
    client: TestClient, monkeypatch
) -> None:
    """A repeated topic must not spend tokens re-running the pipeline."""
    payload = {"topic": "replay me"}
    client.post("/api/research", json=payload)

    def fail(*_a, **_k):
        raise AssertionError("a cached replay must not build an LLM")

    monkeypatch.setattr(api_module, "_resolve_llm", fail)

    with client.stream("POST", "/api/research/stream", json=payload) as resp:
        events = []
        payloads = []
        for line in resp.iter_lines():
            if line.startswith("event: "):
                events.append(line[len("event: ") :].strip())
            elif line.startswith("data: "):
                payloads.append(json.loads(line[len("data: ") :]))

    assert events[-1] == "run_completed"
    assert events.count("stage_completed") == 7
    assert payloads[-1]["result"]["cached"] is True
    assert payloads[-1]["result"]["report"]


def test_stream_bypasses_the_cache_when_asked(client: TestClient) -> None:
    payload = {"topic": "no cache please"}
    client.post("/api/research", json=payload)

    with client.stream(
        "POST", "/api/research/stream", json={**payload, "use_cache": False}
    ) as resp:
        events = [
            line[len("event: ") :].strip()
            for line in resp.iter_lines()
            if line.startswith("event: ")
        ]

    assert "token" in events
    assert events.count("token") > 1, "a live run streams many tokens, a replay sends one"


def test_stream_times_out_a_stalled_run(client: TestClient, monkeypatch) -> None:
    """A stage stuck in rate-limit backoff emits nothing; the budget must still fire."""
    import argus.pipeline as pipeline_module
    from argus.pipeline import PipelineEvent

    async def stalling_pipeline(*_a, **_k):
        yield PipelineEvent("run_started", data={"run_id": "x", "topic": "t"})
        await asyncio.sleep(30)  # longer than the budget below
        yield PipelineEvent("run_completed", data={"result": {}})

    monkeypatch.setattr(api_module.settings, "pipeline_timeout_seconds", 1)
    monkeypatch.setattr(api_module, "run_pipeline", stalling_pipeline)
    monkeypatch.setattr(pipeline_module, "run_pipeline", stalling_pipeline)

    with client.stream("POST", "/api/research/stream", json={"topic": "stalled run"}) as resp:
        events = [
            line[len("event: ") :].strip()
            for line in resp.iter_lines()
            if line.startswith("event: ")
        ]

    assert events[-1] == "run_failed"
    assert "run_completed" not in events


PDF_PAYLOAD = {
    "topic": "Rare earth export controls",
    "report": "## Executive Summary\n\nRefining is concentrated.",
    "critic": "Overall Score: 6/10",
    "scores": {"overall": 6.0},
    "sources": [{"url": "https://example.com/a", "title": "Example"}],
}


def test_export_pdf_returns_a_downloadable_document(client: TestClient) -> None:
    resp = client.post("/api/export/pdf", json=PDF_PAYLOAD)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert ".pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-")


def test_export_pdf_filename_is_derived_from_the_topic(client: TestClient) -> None:
    resp = client.post("/api/export/pdf", json={**PDF_PAYLOAD, "topic": "Why RNA / vaccines?!"})
    assert 'filename="why-rna-vaccines.pdf"' in resp.headers["content-disposition"]


def test_export_pdf_rejects_an_oversized_report(client: TestClient) -> None:
    """The endpoint must not become a general-purpose PDF service."""
    resp = client.post("/api/export/pdf", json={**PDF_PAYLOAD, "report": "x" * 300_000})
    assert resp.status_code == 422


def test_export_pdf_requires_a_report(client: TestClient) -> None:
    assert client.post("/api/export/pdf", json={"topic": "no report"}).status_code == 422
