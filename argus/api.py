"""FastAPI application.

Three surfaces:

* ``POST /api/research/stream`` - server-sent events, the primary path. Progress
  shown in the UI is driven entirely by these events.
* ``POST /api/research`` - blocking JSON, for scripts and for clients that cannot
  consume a stream.
* ``GET /api/models`` - the model catalogue, so the frontend never hard-codes one.

``POST /research`` is retained as a deprecated alias of the blocking endpoint so
existing deployments keep working.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict, defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from argus import __version__
from argus.config import settings
from argus.llm import (
    DEFAULT_MODEL,
    MissingCredentialsError,
    ModelNotFoundError,
    get_llm,
    list_models,
    resolve_spec,
)
from argus.pdf import build_pdf
from argus.pipeline import STAGES, run_pipeline, run_pipeline_collected

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("argus.api")


# -- Rate limiting -----------------------------------------------------------


class SlidingWindowLimiter:
    """Per-client sliding window. In-process, which is correct for a single worker.

    A multi-worker or multi-instance deployment needs a shared store (Redis); this
    is deliberately simple and is documented as such.
    """

    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        async with self._lock:
            now = time.time()
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False, int(self.window - (now - hits[0])) + 1
            hits.append(now)
            if len(self._hits) > 5000:  # crude memory bound
                for stale in [k for k, v in self._hits.items() if not v][:1000]:
                    del self._hits[stale]
            return True, 0


limiter = SlidingWindowLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(request: Request) -> None:
    allowed, retry_after = await limiter.check(client_key(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit reached. Try again in {retry_after}s, or supply your own API key.",
            headers={"Retry-After": str(retry_after)},
        )


# -- Result cache ------------------------------------------------------------


class TTLCache:
    def __init__(self, max_entries: int, ttl: int) -> None:
        self.max_entries = max_entries
        self.ttl = ttl
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.time() - stored_at > self.ttl:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)


cache = TTLCache(settings.cache_max_entries, settings.cache_ttl_seconds)

TIMEOUT_MESSAGE = (
    "The run exceeded its time budget. Free model tiers throttle heavily; "
    "try a narrower topic, a smaller model, or your own API key."
)


def cache_key(topic: str, model: str) -> str:
    return f"{model}::{topic.strip().lower()}"


# -- Schemas -----------------------------------------------------------------


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="The subject to research.")
    model: str = Field(default=DEFAULT_MODEL, description="Model id from /api/models.")
    api_key: str | None = Field(default=None, description="Optional caller-supplied provider key.")
    use_cache: bool = True

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, v: str) -> str:
        topic = " ".join(v.split())
        if len(topic) < settings.min_topic_length:
            raise ValueError(f"Topic must be at least {settings.min_topic_length} characters.")
        if len(topic) > settings.max_topic_length:
            raise ValueError(f"Topic must be at most {settings.max_topic_length} characters.")
        return topic

    @field_validator("api_key")
    @classmethod
    def _clean_key(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


class ExportRequest(BaseModel):
    """A finished run, handed back for rendering.

    The client posts the result rather than a run id because runs are not yet
    persisted. Field sizes are capped so this cannot be used as a general-purpose
    PDF service.
    """

    topic: str = Field(..., max_length=500)
    report: str = Field(..., max_length=200_000)
    critic: str = Field(default="", max_length=100_000)
    factcheck: str = Field(default="", max_length=100_000)
    model_label: str = Field(default="", max_length=120)
    total_ms: int = Field(default=0, ge=0)
    scores: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    pages: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    include_appendix: bool = True


# -- App ---------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("ARGUS %s starting", __version__)
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY is not set - the search stage will fail.")
    if settings.cors_origins == ["*"]:
        logger.warning(
            "CORS is open to all origins. Set ALLOWED_ORIGINS to your frontend URL in production."
        )
    yield


app = FastAPI(
    title="ARGUS Research API",
    version=__version__,
    description="Multi-agent research pipeline: search, read, write, critique.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def _resolve_llm(req: ResearchRequest):
    try:
        return get_llm(req.model, req.api_key)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingCredentialsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Model initialisation failed")
        raise HTTPException(status_code=400, detail=f"Could not initialise model: {exc}") from exc


@app.get("/", tags=["meta"])
def health() -> dict[str, Any]:
    return {
        "status": "online",
        "service": "ARGUS Research API",
        "version": __version__,
        "search_ready": bool(settings.tavily_api_key),
        "models_ready": [m["id"] for m in list_models() if m["ready"]],
    }


@app.get("/api/models", tags=["meta"])
def models() -> dict[str, Any]:
    return {"models": list_models(), "default": DEFAULT_MODEL}


@app.get("/api/stages", tags=["meta"])
def stages() -> dict[str, Any]:
    return {"stages": list(STAGES)}


@app.post("/api/research", tags=["research"], dependencies=[Depends(enforce_rate_limit)])
async def research(req: ResearchRequest) -> dict[str, Any]:
    """Run the pipeline to completion and return the full result."""
    key = cache_key(req.topic, req.model)
    if settings.cache_enabled and req.use_cache and not req.api_key:
        hit = cache.get(key)
        if hit is not None:
            logger.info("Cache hit for %s", key)
            return {**hit, "cached": True}

    llm = _resolve_llm(req)
    try:
        result = await asyncio.wait_for(
            run_pipeline_collected(req.topic, llm), timeout=settings.pipeline_timeout_seconds
        )
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="The pipeline exceeded its time budget. Try a narrower topic or a faster model.",
        ) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    if settings.cache_enabled and not req.api_key:
        cache.set(key, result)
    return {**result, "cached": False}


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def replay(result: dict[str, Any]) -> AsyncIterator[str]:
    """Re-emit a cached run as a stream, so a repeat topic is instant.

    The client renders identically whether a run is live or replayed. Timings are
    the ones the original run actually recorded, and the timeline is reconstructed
    from them rather than re-simulated.
    """
    timings = result.get("timings_ms", {})
    now = time.time()
    yield _sse(
        "run_started",
        {
            "run_id": result.get("run_id"),
            "topic": result.get("topic"),
            "ts": now,
            "cached": True,
        },
    )

    # Sequential stages run back to back; the review stages all began once the
    # report was finished. That is the shape the original run had.
    head = ["search", "read", "write"]
    offset = 0.0
    for stage in head:
        duration = timings.get(stage, 0)
        yield _sse("stage_started", {"stage": stage, "ts": now + offset / 1000})
        offset += duration
        yield _sse(
            "stage_completed",
            {
                "stage": stage,
                "ts": now + offset / 1000,
                "duration_ms": duration,
                **_replay_extras(stage, result),
            },
        )

    for stage in ["critic", "factcheck", "credibility", "followup"]:
        duration = timings.get(stage, 0)
        yield _sse("stage_started", {"stage": stage, "ts": now + offset / 1000})
        yield _sse(
            "stage_completed",
            {
                "stage": stage,
                "ts": now + (offset + duration) / 1000,
                "duration_ms": duration,
                "text": result.get(stage, ""),
            },
        )

    yield _sse("token", {"stage": "write", "text": result.get("report", "")})
    yield _sse("run_completed", {"result": {**result, "cached": True}, "ts": time.time()})


def _replay_extras(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    if stage == "search":
        return {"sources": result.get("sources", []), "count": len(result.get("sources", []))}
    if stage == "read":
        return {"pages": result.get("pages", [])}
    return {}


@app.post("/api/research/stream", tags=["research"], dependencies=[Depends(enforce_rate_limit)])
async def research_stream(req: ResearchRequest, request: Request) -> StreamingResponse:
    """Stream the run as server-sent events.

    POST rather than GET so the optional API key travels in the body and never
    lands in a URL, an access log or a browser history entry.
    """
    spec = resolve_spec(req.model)
    cached = None
    if settings.cache_enabled and req.use_cache and not req.api_key:
        cached = cache.get(cache_key(req.topic, req.model))

    # A cache hit still needs a model, unless we are replaying, in which case no
    # provider call is made at all and a missing key must not block the replay.
    llm = None if cached else _resolve_llm(req)

    async def generate() -> AsyncIterator[str]:
        yield _sse("open", {"model": spec.id, "model_label": spec.label, "topic": req.topic})

        if cached:
            async for frame in replay(cached):
                yield frame
            return

        deadline = time.monotonic() + settings.pipeline_timeout_seconds
        events = run_pipeline(req.topic, llm)
        try:
            while True:
                # The budget is enforced around the *wait* for the next event, not
                # only between events. A stage sleeping through a rate-limit backoff
                # emits nothing, and a check that only ran on arrival would let the
                # run overrun the budget indefinitely.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    yield _sse("run_failed", {"error": TIMEOUT_MESSAGE})
                    return
                try:
                    event = await asyncio.wait_for(anext(events), timeout=remaining)
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    yield _sse("run_failed", {"error": TIMEOUT_MESSAGE})
                    return

                if await request.is_disconnected():
                    logger.info("Client disconnected; abandoning run.")
                    return
                if event.type == "run_completed" and settings.cache_enabled and not req.api_key:
                    cache.set(cache_key(req.topic, req.model), event.data["result"])
                yield _sse(event.type, {"stage": event.stage, "ts": event.ts, **event.data})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Streaming run failed")
            yield _sse("run_failed", {"error": str(exc)})
        finally:
            await events.aclose()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/export/pdf", tags=["export"], dependencies=[Depends(enforce_rate_limit)])
def export_pdf(req: ExportRequest) -> Response:
    """Render a finished run as a typeset PDF."""
    try:
        payload = build_pdf(req.model_dump(), include_appendix=req.include_appendix)
    except Exception as exc:
        logger.exception("PDF rendering failed")
        raise HTTPException(status_code=500, detail=f"Could not render the PDF: {exc}") from exc

    stem = re.sub(r"[^a-z0-9]+", "-", req.topic.lower()).strip("-")[:40] or "research"
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.pdf"',
            "Content-Length": str(len(payload)),
        },
    )


@app.post(
    "/research", tags=["research"], deprecated=True, dependencies=[Depends(enforce_rate_limit)]
)
async def research_legacy(req: ResearchRequest) -> dict[str, Any]:
    """Deprecated alias of ``POST /api/research``, kept for older clients."""
    result = await research(req)
    return {
        **result,
        "feedback": result.get("critic", ""),
        "followup_questions": result.get("followup", ""),
    }
