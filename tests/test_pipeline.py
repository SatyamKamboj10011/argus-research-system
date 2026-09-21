"""Tests for response parsing and pipeline event sequencing."""

from __future__ import annotations

import pytest

from argus.pipeline import (
    parse_fact_check,
    parse_followups,
    parse_scores,
    public_result,
    run_pipeline,
)

WELL_FORMED_CRITIQUE = """Overall Score: 7.5/10

Category Scores:
- Factual Accuracy: 8/10
- Depth of Analysis: 7/10
- Structure & Clarity: 9/10
- Use of Sources: 6/10
- Completeness: 7/10
- Professional Quality: 8/10

One-Line Verdict: Well organised but thinly sourced.

Recommendation: NEEDS REVISION - needs primary sources.
"""


def test_parse_scores_extracts_every_field() -> None:
    scores = parse_scores(WELL_FORMED_CRITIQUE)
    assert scores["overall"] == 7.5
    assert scores["categories"]["Use of Sources"] == 6.0
    assert len(scores["categories"]) == 6
    assert scores["recommendation"] == "NEEDS REVISION"
    assert scores["verdict"] == "Well organised but thinly sourced."


@pytest.mark.parametrize("text", ["", "The report was quite good, I'd say 8 out of 10."])
def test_parse_scores_degrades_gracefully(text: str) -> None:
    """A model that ignores the format must not break the run."""
    result = parse_scores(text)
    assert "overall" not in result or isinstance(result["overall"], float)
    assert result.get("categories", {}) == {}


def test_parse_scores_clamps_out_of_range() -> None:
    assert parse_scores("Overall Score: 47/10")["overall"] == 10.0


def test_parse_scores_accepts_markdown_bullets_and_and_spelling() -> None:
    scores = parse_scores("* Structure and Clarity: 5/10\n- Completeness: 4/10")
    assert scores["categories"]["Structure & Clarity"] == 5.0
    assert scores["categories"]["Completeness"] == 4.0


def test_parse_fact_check() -> None:
    out = parse_fact_check("Fact Check Score: 6.5/10\nVerdict: USE WITH CAUTION")
    assert out == {"score": 6.5, "verdict": "USE WITH CAUTION"}


def test_parse_fact_check_empty() -> None:
    assert parse_fact_check("") == {}


def test_parse_followups_handles_both_numbering_styles() -> None:
    questions = parse_followups(
        "Here you go:\n1. What drives refining capacity growth?\n"
        "2) How exposed is the EU to supply shocks?\n"
        "3. short\n"
    )
    assert questions == [
        "What drives refining capacity growth?",
        "How exposed is the EU to supply shocks?",
    ]


def test_parse_followups_caps_at_eight() -> None:
    text = "\n".join(f"{i}. A sufficiently long question number {i}?" for i in range(1, 15))
    assert len(parse_followups(text)) == 8


def test_public_result_never_leaks_internal_state() -> None:
    result = public_result({"topic": "x", "report": "r", "secret_key": "sk-123", "pages": []})
    assert "secret_key" not in result
    assert result["topic"] == "x"
    assert set(result) >= {"report", "critic", "sources", "scores", "timings_ms"}


# -- Event sequencing with a stubbed model -----------------------------------


@pytest.mark.asyncio
async def test_pipeline_emits_ordered_events(
    monkeypatch, fake_llm, fake_search, fake_fetch
) -> None:
    events = [e async for e in run_pipeline("rare earth minerals", fake_llm)]
    types = [e.type for e in events]

    assert types[0] == "run_started"
    assert types[-1] == "run_completed"

    started = {e.stage for e in events if e.type == "stage_started"}
    completed = {e.stage for e in events if e.type == "stage_completed"}
    assert {"search", "read", "write", "critic", "factcheck", "credibility", "followup"} <= started
    assert started == completed, "every started stage must reach a terminal event"

    assert any(e.type == "token" for e in events), "the write stage must stream tokens"

    result = events[-1].data["result"]
    assert result["report"]
    assert result["scores"]["overall"] == 7.5
    assert result["sources"]
    assert result["timings_ms"]["search"] >= 0


@pytest.mark.asyncio
async def test_pipeline_fails_cleanly_when_search_is_unavailable(
    monkeypatch, fake_llm, fake_fetch
) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("TAVILY_API_KEY is not configured on the server.")

    monkeypatch.setattr("argus.pipeline.search_web", boom)
    monkeypatch.setattr("argus.pipeline.create_agent", lambda **_k: _RaisingAgent())

    events = [e async for e in run_pipeline("topic", fake_llm)]
    assert events[-1].type == "run_failed"
    assert "Search failed" in events[-1].data["error"]


class _RaisingAgent:
    def invoke(self, _payload):
        raise RuntimeError("no tools available")


@pytest.mark.asyncio
async def test_writer_falls_back_when_streaming_yields_nothing(
    monkeypatch, fake_llm, fake_search, fake_fetch
) -> None:
    """Reasoning models can stream only hidden thought and no content chunks."""
    import argus.pipeline as pipeline_module

    class SilentStream:
        """Streams nothing, but returns a report when invoked normally."""

        def __init__(self, inner):
            self.inner = inner

        async def astream(self, _payload):
            return
            yield  # pragma: no cover - makes this an async generator

        async def ainvoke(self, payload):
            return await self.inner.ainvoke(payload)

    real_build = pipeline_module.build_chain

    def build(prompt, llm):
        chain = real_build(prompt, llm)
        return SilentStream(chain) if prompt is pipeline_module.WRITER_PROMPT else chain

    monkeypatch.setattr(pipeline_module, "build_chain", build)

    events = [e async for e in run_pipeline("a topic", fake_llm)]
    assert events[-1].type == "run_completed"
    assert "Executive Summary" in events[-1].data["result"]["report"]
