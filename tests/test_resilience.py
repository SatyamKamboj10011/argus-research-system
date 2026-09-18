"""Tests for payload clamping, error translation and rate-limit backoff."""

from __future__ import annotations

import pytest

from argus.config import settings
from argus.pipeline import (
    _is_rate_limited,
    _retry_after_seconds,
    ainvoke_with_retry,
    clamp,
    friendly_error,
)

GROQ_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-120b` on tokens per minute (TPM): Limit 8000, Used 4684, "
    "Requested 4103. Please try again in 5.9025s.', 'code': 'rate_limit_exceeded'}}"
)
GROQ_413 = (
    "Error code: 413 - {'error': {'message': 'Request too large for model "
    "`openai/gpt-oss-120b` on tokens per minute (TPM): Limit 8000, Requested 8516'}}"
)


def test_clamp_leaves_short_text_untouched() -> None:
    assert clamp("short", 100) == "short"


def test_clamp_marks_the_cut() -> None:
    out = clamp("x" * 500, 100)
    assert out.startswith("x" * 100)
    assert "truncated at 100 characters" in out


def test_clamp_defaults_to_the_configured_budget() -> None:
    assert len(clamp("y" * 99_999)) <= settings.max_research_chars + 60


@pytest.mark.parametrize("raw", [GROQ_429, GROQ_413, "429 Too Many Requests"])
def test_rate_limit_errors_are_detected(raw: str) -> None:
    assert _is_rate_limited(Exception(raw))


def test_non_rate_limit_errors_are_not_retried() -> None:
    assert not _is_rate_limited(Exception("connection reset by peer"))


def test_backoff_uses_the_providers_own_hint() -> None:
    assert _retry_after_seconds(Exception(GROQ_429), 0) == pytest.approx(6.4, abs=0.01)


def test_backoff_falls_back_to_exponential() -> None:
    assert _retry_after_seconds(Exception("429"), 0) == 1.0
    assert _retry_after_seconds(Exception("429"), 3) == 8.0


def test_backoff_is_capped() -> None:
    assert _retry_after_seconds(Exception("try again in 900s"), 0) == 30.0
    assert _retry_after_seconds(Exception("429"), 12) == 30.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (GROQ_429, "rate limit"),
        ("Error: model_not_found", "no longer offered"),
        ("401 invalid api key", "rejected by the provider"),
        ("insufficient_quota for this key", "no remaining quota"),
        ("Request timed out", "timed out"),
    ],
)
def test_friendly_error_translates_provider_noise(raw: str, expected: str) -> None:
    assert expected in friendly_error(Exception(raw)).lower()


def test_friendly_error_passes_through_unknown_errors_truncated() -> None:
    assert friendly_error(Exception("z" * 900)) == "z" * 400


class _Chain:
    """Fails with a rate-limit error `failures` times, then succeeds."""

    def __init__(self, failures: int, error: str = GROQ_429) -> None:
        self.failures = failures
        self.error = error
        self.calls = 0

    async def ainvoke(self, _payload):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(self.error)
        return "ok"


@pytest.mark.asyncio
async def test_retry_recovers_from_a_transient_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr("argus.pipeline.asyncio.sleep", _no_sleep)
    chain = _Chain(failures=2)
    assert await ainvoke_with_retry(chain, {}, "critic") == "ok"
    assert chain.calls == 3


@pytest.mark.asyncio
async def test_retry_gives_up_after_the_configured_limit(monkeypatch) -> None:
    monkeypatch.setattr("argus.pipeline.asyncio.sleep", _no_sleep)
    chain = _Chain(failures=99)
    with pytest.raises(RuntimeError):
        await ainvoke_with_retry(chain, {}, "critic")
    assert chain.calls == settings.llm_max_retries + 1


@pytest.mark.asyncio
async def test_non_rate_limit_errors_fail_immediately(monkeypatch) -> None:
    monkeypatch.setattr("argus.pipeline.asyncio.sleep", _no_sleep)
    chain = _Chain(failures=99, error="model_not_found")
    with pytest.raises(RuntimeError):
        await ainvoke_with_retry(chain, {}, "critic")
    assert chain.calls == 1, "a non-transient error must not be retried"


async def _no_sleep(_seconds: float) -> None:
    return None
