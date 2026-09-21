"""Tests for PDF rendering.

The document is binary, so these assert on structure and on the things that could
silently corrupt it — unescaped markup, injected tags, malformed input — rather
than on pixels.
"""

from __future__ import annotations

import pytest

from argus.pdf import (
    _inline,
    _markdown_flowables,
    _strip_scores,
    _styles,
    build_pdf,
    winansi,
)

RESULT = {
    "topic": "Rare earth export controls",
    "model_label": "GPT-OSS 120B",
    "total_ms": 81_000,
    "report": (
        "## Executive Summary\n\n"
        "Refining is **concentrated** and costs are *rising*.\n\n"
        "## Key Findings\n\n"
        "### 1. Supply is narrow\n\n"
        "- One country dominates\n"
        "- Licensing is slow\n\n"
        "1. First\n2. Second\n\n"
        "See [the source](https://example.com/a).\n"
    ),
    "critic": "Overall Score: 6/10\n\nStrengths:\n- Clear structure",
    "factcheck": "Fact Check Score: 7/10\nVerdict: MOSTLY RELIABLE",
    "scores": {
        "overall": 6.0,
        "recommendation": "NEEDS REVISION",
        "verdict": "Readable but under-sourced.",
        "categories": {"Factual Accuracy": 7.0, "Use of Sources": 4.0},
    },
    "sources": [{"url": "https://example.com/a", "title": "Example source"}],
    "pages": [{"source_url": "https://example.com/a", "chars": 4000, "error": None}],
}


def test_build_pdf_produces_a_valid_document() -> None:
    pdf = build_pdf(RESULT)
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 2000


def test_appendix_can_be_omitted() -> None:
    assert len(build_pdf(RESULT, include_appendix=False)) < len(build_pdf(RESULT))


def test_build_pdf_survives_an_empty_run() -> None:
    """A run that failed before the writer must still render, not raise."""
    pdf = build_pdf({"topic": "Nothing", "report": ""})
    assert pdf.startswith(b"%PDF-")


def test_build_pdf_handles_a_missing_topic() -> None:
    assert build_pdf({}).startswith(b"%PDF-")


# -- Inline markup -----------------------------------------------------------


def test_inline_escapes_before_formatting() -> None:
    """Scraped text reaches this function; raw markup must not survive into the PDF."""
    out = _inline("5 < 6 & 7 > 2")
    assert "&lt;" in out and "&amp;" in out and "&gt;" in out
    assert "<b>" not in out


def test_inline_cannot_inject_reportlab_tags() -> None:
    out = _inline('<para backColor="red">boom</para><onDraw name="evil"/>')
    assert "<para" not in out
    assert "<onDraw" not in out
    assert "&lt;para" in out


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("**bold**", "<b>bold</b>"),
        ("*italic*", "<i>italic</i>"),
        ("`code`", 'face="Courier"'),
        ("[text](https://example.com)", 'href="https://example.com"'),
    ],
)
def test_inline_formatting(source: str, expected: str) -> None:
    assert expected in _inline(source)


def test_inline_leaves_bare_asterisks_alone() -> None:
    """Multiplication and footnote markers are not emphasis."""
    assert "<i>" not in _inline("3 * 4 = 12")


def test_link_text_with_markup_is_still_escaped() -> None:
    out = _inline("[a <b> c](https://example.com)")
    assert "&lt;b&gt;" in out


# -- Block parsing -----------------------------------------------------------


def test_markdown_produces_flowables_for_each_block() -> None:
    styles = _styles()
    flowables = _markdown_flowables(RESULT["report"], styles)
    assert len(flowables) >= 7


def test_markdown_handles_empty_input() -> None:
    assert _markdown_flowables("", _styles()) == []


def test_markdown_separates_ordered_and_unordered_lists() -> None:
    """A bullet list followed by a numbered list must not merge into one."""
    from reportlab.platypus import ListFlowable

    flowables = _markdown_flowables("- a\n- b\n\n1. one\n2. two\n", _styles())
    lists = [f for f in flowables if isinstance(f, ListFlowable)]
    assert len(lists) == 2


def test_strip_scores_removes_the_numeric_block() -> None:
    out = _strip_scores("Overall Score: 6/10\n\nStrengths:\n- Clear\n\nUse of Sources: 4/10")
    assert "Overall Score" not in out
    assert "Use of Sources: 4/10" not in out
    assert "Clear" in out


# -- WinAnsi safety ----------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("under‑supported", "under-supported"),
        ("42 %", "42 %"),
        ("cost‐benefit", "cost-benefit"),
        ("≈ 5", "~ 5"),
        ("x ≥ 3", "x >= 3"),
        ("a​b", "ab"),
        ("ﬁnal", "final"),
        ("5 − 3", "5 - 3"),
    ],
)
def test_winansi_substitutions(source: str, expected: str) -> None:
    assert winansi(source) == expected


def test_winansi_preserves_characters_the_font_has() -> None:
    """cp1252 covers curly quotes, dashes and the euro sign — keep them."""
    text = "“quoted” — café €5 …"
    assert winansi(text) == text


def test_winansi_output_is_always_encodable() -> None:
    """The guarantee that matters: nothing reaching the PDF can be a tofu box."""
    hostile = "你好 مرحبا ☃ \U0001f600 αβγ"
    winansi(hostile).encode("cp1252")


def test_winansi_handles_empty() -> None:
    assert winansi("") == ""


def test_pdf_of_a_real_report_has_no_unencodable_text() -> None:
    """Regression: a live report contained 58 non-breaking hyphens."""
    report = "## Summary\n\nA low‑carbon, state‑level review of 42 % growth.\n"
    pdf = build_pdf({"topic": "Cost‑benefit ≈ review", "report": report})
    assert pdf.startswith(b"%PDF-")
