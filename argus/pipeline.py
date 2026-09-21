"""The research pipeline.

Exposes an async generator that yields :class:`PipelineEvent` objects as work
actually happens. The API streams those events straight to the browser, so the
progress a user sees is the real state of the run rather than a client-side
animation.

Stage graph::

    search ──► read ──► write ──┬──► critic
                                ├──► fact-check
                                ├──► credibility
                                └──► follow-up

The four review stages depend only on the report, so they run concurrently.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage

from argus.config import settings
from argus.prompts import (
    CREDIBILITY_PROMPT,
    CRITIC_PROMPT,
    FACT_CHECK_PROMPT,
    FOLLOWUP_PROMPT,
    WRITER_PROMPT,
    build_chain,
)
from argus.tools import SearchResult, fetch_page, format_results, search_web, web_search

logger = logging.getLogger(__name__)

STAGES: tuple[dict[str, str], ...] = (
    {"id": "search", "label": "Search", "detail": "ReAct agent queries the live web"},
    {"id": "read", "label": "Read", "detail": "Parallel fetch and extract of top sources"},
    {"id": "write", "label": "Write", "detail": "Synthesise the structured report"},
    {"id": "critic", "label": "Critique", "detail": "Score the report across six dimensions"},
    {"id": "factcheck", "label": "Fact-check", "detail": "Verify claims against sources"},
    {"id": "credibility", "label": "Credibility", "detail": "Rate each source's authority"},
    {"id": "followup", "label": "Follow-up", "detail": "Propose the next research round"},
)

CATEGORY_LABELS = {
    "factual accuracy": "Factual Accuracy",
    "depth of analysis": "Depth of Analysis",
    "structure & clarity": "Structure & Clarity",
    "structure and clarity": "Structure & Clarity",
    "use of sources": "Use of Sources",
    "completeness": "Completeness",
    "professional quality": "Professional Quality",
}


@dataclass
class PipelineEvent:
    type: str
    stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Response parsing --------------------------------------------------------


def parse_scores(feedback: str) -> dict[str, Any]:
    """Pull the numeric scores out of the critic's response.

    Returns ``{}`` rather than raising when the model drifts from the format, so a
    malformed critique degrades the UI gracefully instead of failing the run.
    """
    if not feedback:
        return {}

    result: dict[str, Any] = {"categories": {}}

    overall = re.search(r"Overall\s+Score\s*:\s*([\d.]+)\s*/\s*10", feedback, re.I)
    if overall:
        with contextlib.suppress(ValueError):
            result["overall"] = round(min(10.0, max(0.0, float(overall.group(1)))), 1)

    for raw_label, value in re.findall(
        r"^[-*\s]*([A-Za-z&\s]+?)\s*:\s*([\d.]+)\s*/\s*10\s*$", feedback, re.I | re.M
    ):
        key = raw_label.strip().lower()
        if key in CATEGORY_LABELS:
            try:
                result["categories"][CATEGORY_LABELS[key]] = round(float(value), 1)
            except ValueError:
                continue

    verdict = re.search(r"One-Line\s+Verdict\s*:\s*(.+)", feedback, re.I)
    if verdict:
        result["verdict"] = verdict.group(1).strip()

    rec = re.search(r"Recommendation\s*:\s*\**\s*(APPROVE|NEEDS REVISION|REJECT)", feedback, re.I)
    if rec:
        result["recommendation"] = rec.group(1).upper()

    return result


def parse_fact_check(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    score = re.search(r"Fact\s*Check\s*Score\s*:\s*([\d.]+)\s*/\s*10", text or "", re.I)
    if score:
        with contextlib.suppress(ValueError):
            out["score"] = round(float(score.group(1)), 1)
    verdict = re.search(
        r"Verdict\s*:\s*\**\s*(RELIABLE|MOSTLY RELIABLE|USE WITH CAUTION|UNRELIABLE)",
        text or "",
        re.I,
    )
    if verdict:
        out["verdict"] = verdict.group(1).upper()
    return out


def parse_followups(text: str) -> list[str]:
    if not text:
        return []
    questions = [
        re.sub(r"^\d+[.)]\s*", "", line.strip())
        for line in text.splitlines()
        if re.match(r"^\s*\d+[.)]", line)
    ]
    return [q for q in questions if len(q) > 8][:8]


def clamp(text: str, limit: int | None = None) -> str:
    """Trim a payload to a character budget, marking where it was cut."""
    limit = limit or settings.max_research_chars
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncated at {limit} characters ...]"


def friendly_error(exc: Exception) -> str:
    """Turn a provider's raw error payload into something a user can act on."""
    raw = str(exc)
    lowered = raw.lower()
    if "rate_limit" in lowered or "429" in lowered or "request too large" in lowered:
        return (
            "The model provider's rate limit was hit. Free tiers cap tokens per minute - "
            "wait a moment and retry, pick a smaller model, or supply your own API key."
        )
    if "model_not_found" in lowered or "does not exist" in lowered:
        return "That model is no longer offered by the provider. Pick another from the model list."
    if "authentication" in lowered or "invalid api key" in lowered or "401" in lowered:
        return "The API key was rejected by the provider. Check the key and try again."
    if "insufficient_quota" in lowered or "billing" in lowered:
        return "The provider reports no remaining quota on this key."
    if "timeout" in lowered or "timed out" in lowered:
        return "The provider timed out. Try a narrower topic or a faster model."
    return raw[:400]


_RATE_LIMIT_MARKERS = ("rate_limit", "rate limit", "429", "too many requests", "request too large")


def _is_rate_limited(exc: Exception) -> bool:
    return any(marker in str(exc).lower() for marker in _RATE_LIMIT_MARKERS)


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """Honour the provider's own 'try again in Ns' hint when it gives one."""
    match = re.search(r"try again in ([\d.]+)\s*s", str(exc), re.I)
    if match:
        try:
            return min(30.0, float(match.group(1)) + 0.5)
        except ValueError:
            pass
    return min(30.0, 2.0**attempt)


async def ainvoke_with_retry(chain, payload: dict[str, Any], label: str) -> str:
    """Invoke a chain, backing off when the provider reports a token-rate limit.

    Free tiers meter tokens per minute, so a burst of parallel review chains is
    throttled rather than rejected outright. Retrying on the provider's own hint
    turns a hard stage failure into a short wait.
    """
    last: Exception | None = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            return await chain.ainvoke(payload)
        except Exception as exc:
            last = exc
            if not _is_rate_limited(exc) or attempt == settings.llm_max_retries:
                raise
            wait = _retry_after_seconds(exc, attempt)
            logger.info("%s rate limited; retrying in %.1fs (attempt %d)", label, wait, attempt + 1)
            await asyncio.sleep(wait)
    raise last  # pragma: no cover - loop always returns or raises


def _sources_from_agent(messages: list[Any]) -> list[SearchResult]:
    """Recover structured sources from whatever the search agent actually retrieved."""
    seen: dict[str, SearchResult] = {}
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        for block in content.split("-----"):
            title = re.search(r"Title:\s*(.+)", block)
            url = re.search(r"URL:\s*(\S+)", block)
            snippet = re.search(r"Snippet:\s*([\s\S]+)", block)
            if url and url.group(1) not in seen:
                from urllib.parse import urlparse

                u = url.group(1).strip()
                seen[u] = SearchResult(
                    title=title.group(1).strip() if title else "Untitled",
                    url=u,
                    snippet=snippet.group(1).strip()[:400] if snippet else "",
                    domain=urlparse(u).netloc,
                )
    return list(seen.values())


# -- The pipeline ------------------------------------------------------------


async def run_pipeline(topic: str, llm, run_id: str | None = None) -> AsyncIterator[PipelineEvent]:
    """Execute a full research run, yielding events as each stage progresses."""
    run_id = run_id or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    state: dict[str, Any] = {"topic": topic, "run_id": run_id}
    timings: dict[str, int] = {}

    yield PipelineEvent(
        "run_started", data={"run_id": run_id, "topic": topic, "stages": list(STAGES)}
    )

    def elapsed(mark: float) -> int:
        return int((time.perf_counter() - mark) * 1000)

    # -- 1. Search -----------------------------------------------------------
    mark = time.perf_counter()
    yield PipelineEvent("stage_started", "search")
    sources: list[SearchResult] = []
    try:
        agent = create_agent(model=llm, tools=[web_search])
        agent_result = await asyncio.to_thread(
            agent.invoke,
            {
                "messages": [
                    (
                        "user",
                        f"Research this topic: {topic}\n\n"
                        "Use the web_search tool. If the first set of results is thin or "
                        "off-target, refine the query and search again (at most 3 searches). "
                        "Then list the most relevant sources you found.",
                    )
                ]
            },
        )
        sources = _sources_from_agent(agent_result.get("messages", []))
        state["search_summary"] = agent_result["messages"][-1].content
    except Exception as exc:
        logger.warning("Search agent failed, falling back to direct search: %s", exc)
        yield PipelineEvent(
            "stage_warning", "search", {"message": f"Agent failed ({exc}); using direct search."}
        )

    if not sources:
        try:
            sources = await asyncio.to_thread(search_web, topic)
            state.setdefault("search_summary", format_results(sources))
        except Exception as exc:
            timings["search"] = elapsed(mark)
            yield PipelineEvent("stage_failed", "search", {"error": friendly_error(exc)})
            yield PipelineEvent(
                "run_failed", data={"error": f"Search failed. {friendly_error(exc)}"}
            )
            return

    state["sources"] = [s.to_dict() for s in sources]
    state["search_results"] = format_results(sources)
    timings["search"] = elapsed(mark)
    yield PipelineEvent(
        "stage_completed",
        "search",
        {"duration_ms": timings["search"], "count": len(sources), "sources": state["sources"]},
    )

    # -- 2. Read -------------------------------------------------------------
    mark = time.perf_counter()
    targets = [s.url for s in sources[: settings.scrape_max_pages]]
    yield PipelineEvent("stage_started", "read", {"targets": targets})

    async def _read(url: str) -> dict[str, Any]:
        # `source_url` is the URL we asked for; `url` is where we landed. They
        # differ whenever a redirect is followed, so clients must correlate a page
        # back to its search result on the former.
        try:
            page = await asyncio.to_thread(fetch_page, url)
            return {**page, "source_url": url}
        except Exception as exc:
            logger.info("Could not read %s: %s", url, exc)
            return {"url": url, "source_url": url, "error": str(exc)}

    pages = await asyncio.gather(*(_read(u) for u in targets)) if targets else []
    ok_pages = [p for p in pages if "error" not in p and p.get("text")]
    state["pages"] = pages
    state["scraped_content"] = (
        "\n\n".join(f"# {p['title']}\nSource: {p['url']}\n\n{p['text']}" for p in ok_pages)
        or "No pages could be read; the report relies on search snippets alone."
    )
    timings["read"] = elapsed(mark)
    yield PipelineEvent(
        "stage_completed",
        "read",
        {
            "duration_ms": timings["read"],
            "read": len(ok_pages),
            "attempted": len(targets),
            "pages": [
                {
                    "url": p["url"],
                    "title": p.get("title", ""),
                    "chars": p.get("chars", 0),
                    "error": p.get("error"),
                }
                for p in pages
            ],
        },
    )

    # -- 3. Write ------------------------------------------------------------
    mark = time.perf_counter()
    yield PipelineEvent("stage_started", "write")
    research = clamp(
        f"Search results:\n{state['search_results']}\n\n"
        f"Full page content:\n{state['scraped_content']}"
    )
    report_parts: list[str] = []
    try:
        writer = build_chain(WRITER_PROMPT, llm)
        async for chunk in writer.astream({"topic": topic, "research": research}):
            if chunk:
                report_parts.append(chunk)
                yield PipelineEvent("token", "write", {"text": chunk})
        state["report"] = "".join(report_parts).strip()
        if not state["report"]:
            # Reasoning models sometimes stream only their hidden chain of thought
            # and emit no content chunks. One non-streaming retry recovers the
            # report rather than failing a run that has already done all the work.
            logger.info("Writer produced no streamed content; retrying without streaming.")
            state["report"] = (
                await ainvoke_with_retry(writer, {"topic": topic, "research": research}, "write")
            ).strip()
            if state["report"]:
                yield PipelineEvent("token", "write", {"text": state["report"]})
        if not state["report"]:
            raise RuntimeError("The model returned an empty report.")
    except Exception as exc:
        timings["write"] = elapsed(mark)
        yield PipelineEvent("stage_failed", "write", {"error": friendly_error(exc)})
        yield PipelineEvent(
            "run_failed", data={"error": f"Report generation failed. {friendly_error(exc)}"}
        )
        return

    timings["write"] = elapsed(mark)
    yield PipelineEvent(
        "stage_completed", "write", {"duration_ms": timings["write"], "chars": len(state["report"])}
    )

    # -- 4-7. Review stages, concurrently ------------------------------------
    # Fact-checking sees both the report and its sources, so each half gets a
    # smaller budget to keep a single request inside a free tier's per-minute cap.
    half = settings.max_research_chars // 2
    report_text = state["report"]

    review_specs = (
        ("critic", CRITIC_PROMPT, {"report": clamp(report_text)}),
        (
            "factcheck",
            FACT_CHECK_PROMPT,
            {"report": clamp(report_text, half), "research": clamp(research, half)},
        ),
        ("credibility", CREDIBILITY_PROMPT, {"search_results": clamp(state["search_results"])}),
        ("followup", FOLLOWUP_PROMPT, {"topic": topic, "report": clamp(report_text, half)}),
    )

    queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
    gate = asyncio.Semaphore(settings.review_concurrency)

    async def _review(stage: str, prompt, payload) -> None:
        async with gate:
            stage_mark = time.perf_counter()
            await queue.put(PipelineEvent("stage_started", stage))
            try:
                text = await ainvoke_with_retry(build_chain(prompt, llm), payload, stage)
                state[stage] = text
                timings[stage] = int((time.perf_counter() - stage_mark) * 1000)
                await queue.put(
                    PipelineEvent(
                        "stage_completed",
                        stage,
                        {"duration_ms": timings[stage], "text": text, **_stage_extras(stage, text)},
                    )
                )
            except Exception as exc:
                logger.warning("%s stage failed: %s", stage, exc)
                state[stage] = ""
                timings[stage] = int((time.perf_counter() - stage_mark) * 1000)
                await queue.put(
                    PipelineEvent("stage_failed", stage, {"error": friendly_error(exc)})
                )

    tasks = [asyncio.create_task(_review(*spec)) for spec in review_specs]
    pending = len(tasks)
    completed = 0
    while completed < pending:
        event = await queue.get()
        yield event
        if event.type in ("stage_completed", "stage_failed"):
            completed += 1
    await asyncio.gather(*tasks, return_exceptions=True)

    # -- Done ----------------------------------------------------------------
    state["scores"] = parse_scores(state.get("critic", ""))
    state["fact_check_summary"] = parse_fact_check(state.get("factcheck", ""))
    state["followup_questions"] = parse_followups(state.get("followup", ""))
    state["timings_ms"] = timings
    state["total_ms"] = int((time.perf_counter() - started) * 1000)

    yield PipelineEvent("run_completed", data={"result": public_result(state)})


def _page_summary(page: dict[str, Any]) -> dict[str, Any]:
    """The client-facing shape of a fetched page."""
    return {
        "url": page.get("url"),
        "source_url": page.get("source_url", page.get("url")),
        "title": page.get("title", ""),
        "chars": page.get("chars", 0),
        "error": page.get("error"),
    }


def _stage_extras(stage: str, text: str) -> dict[str, Any]:
    if stage == "critic":
        return {"scores": parse_scores(text)}
    if stage == "factcheck":
        return {"summary": parse_fact_check(text)}
    if stage == "followup":
        return {"questions": parse_followups(text)}
    return {}


def public_result(state: dict[str, Any]) -> dict[str, Any]:
    """The serialisable result payload returned to clients."""
    return {
        "run_id": state.get("run_id"),
        "topic": state.get("topic"),
        "report": state.get("report", ""),
        "critic": state.get("critic", ""),
        "factcheck": state.get("factcheck", ""),
        "credibility": state.get("credibility", ""),
        "followup": state.get("followup", ""),
        "followup_questions": state.get("followup_questions", []),
        "scores": state.get("scores", {}),
        "fact_check_summary": state.get("fact_check_summary", {}),
        "sources": state.get("sources", []),
        "pages": [_page_summary(p) for p in state.get("pages", [])],
        "search_results": state.get("search_results", ""),
        "scraped_content": state.get("scraped_content", ""),
        "timings_ms": state.get("timings_ms", {}),
        "total_ms": state.get("total_ms", 0),
    }


async def run_pipeline_collected(topic: str, llm, run_id: str | None = None) -> dict[str, Any]:
    """Run the pipeline to completion and return only the final result."""
    result: dict[str, Any] | None = None
    error: str | None = None
    async for event in run_pipeline(topic, llm, run_id):
        if event.type == "run_completed":
            result = event.data["result"]
        elif event.type == "run_failed":
            error = event.data.get("error", "Pipeline failed.")
    if error:
        raise RuntimeError(error)
    if result is None:
        raise RuntimeError("Pipeline produced no result.")
    return result
