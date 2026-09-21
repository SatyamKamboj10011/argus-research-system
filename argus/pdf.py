"""Render a finished research run as a PDF.

The app's own surface is dark; a document that will be printed or emailed is not.
This renders a light, typeset document rather than a screenshot of the UI, so the
text stays selectable and the file stays small.

ReportLab is used because it ships as a pure-Python wheel — WeasyPrint and friends
need system libraries that a free-tier host will not have.
"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5f5f5f")
FAINT = colors.HexColor("#8a8a8a")
RULE = colors.HexColor("#d9d9d9")
EMBER = colors.HexColor("#c2390b")
GOOD = colors.HexColor("#1f7a4d")
FAIR = colors.HexColor("#a1720a")
POOR = colors.HexColor("#b03a30")

CATEGORY_ORDER = [
    "Factual Accuracy",
    "Depth of Analysis",
    "Structure & Clarity",
    "Use of Sources",
    "Completeness",
    "Professional Quality",
]


def _score_colour(value: float) -> colors.Color:
    if value >= 8:
        return GOOD
    if value >= 6:
        return FAIR
    return POOR


# -- Text sanitising ---------------------------------------------------------

# ReportLab's built-in fonts are WinAnsi-encoded. Anything outside cp1252 renders
# as a black box, and language models emit these constantly — one real report
# contained 58 non-breaking hyphens and 32 narrow no-break spaces.
_SUBSTITUTIONS = {
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    "⁄": "/",  # fraction slash
    " ": " ",  # no-break space
    " ": " ",  # narrow no-break space
    " ": " ",
    " ": " ",
    " ": " ",  # thin space
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "​": "",  # zero-width space
    "‌": "",
    "‍": "",
    "﻿": "",
    "≈": "~",  # almost equal to
    "≠": "!=",
    "≤": "<=",
    "≥": ">=",
    "≡": "=",
    "→": "->",
    "←": "<-",
    "′": "'",  # prime
    "″": '"',  # double prime
    "➔": "->",
}

_TRANSLATION = str.maketrans(_SUBSTITUTIONS)


def winansi(text: str) -> str:
    """Coerce text into something the built-in PDF fonts can actually draw.

    Explicit substitutions first, then a compatibility decomposition to catch
    ligatures and exotic spacing, then a final pass that drops anything still
    unrepresentable rather than emitting a box.
    """
    if not text:
        return ""

    out = text.translate(_TRANSLATION)
    try:
        out.encode("cp1252")
        return out
    except UnicodeEncodeError:
        pass

    folded = unicodedata.normalize("NFKD", out)
    chars = []
    for ch in folded:
        if unicodedata.combining(ch):
            continue
        try:
            ch.encode("cp1252")
        except UnicodeEncodeError:
            continue
        chars.append(ch)
    return "".join(chars)


# -- Markdown to ReportLab markup --------------------------------------------

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+?)\*(?![*\w])")
_CODE = re.compile(r"`([^`\n]+?)`")


def _inline(text: str) -> str:
    """Convert inline Markdown to ReportLab's mini-HTML.

    Escaping happens first so that content containing ``<`` or ``&`` cannot break
    the markup, or inject tags of its own — the text here comes from a language
    model reading arbitrary web pages.
    """
    out = html.escape(winansi(text), quote=False)
    out = _CODE.sub(r'<font face="Courier" size="9">\1</font>', out)
    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _ITALIC.sub(r"<i>\1</i>", out)
    out = _LINK.sub(
        lambda m: (
            f'<link href="{html.escape(m.group(2), quote=True)}" color="#1f4fd8">'
            f"{m.group(1)}</link>"
        ),
        out,
    )
    return out


def _markdown_flowables(markdown: str, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """A deliberately small Markdown subset: what the writer prompt actually emits."""
    flowables: list[Flowable] = []
    bullets: list[str] = []
    ordered = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            flowables.append(Paragraph(_inline(" ".join(paragraph)), styles["body"]))
            paragraph.clear()

    def flush_bullets() -> None:
        if not bullets:
            return
        flowables.append(
            ListFlowable(
                [
                    ListItem(Paragraph(_inline(item), styles["body"]), leftIndent=12)
                    for item in bullets
                ],
                bulletType="1" if ordered else "bullet",
                bulletFontSize=8,
                bulletColor=FAINT,
                leftIndent=14,
                spaceBefore=2,
                spaceAfter=6,
            )
        )
        bullets.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_bullets()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = len(heading.group(1))
            style = styles["h2"] if level <= 2 else styles["h3"]
            flowables.append(Paragraph(_inline(heading.group(2)), style))
            continue

        if re.match(r"^([-*+])\s+", stripped):
            flush_paragraph()
            if ordered:
                flush_bullets()
            ordered = False
            bullets.append(re.sub(r"^([-*+])\s+", "", stripped))
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            flush_paragraph()
            if not ordered and bullets:
                flush_bullets()
            ordered = True
            bullets.append(re.sub(r"^\d+[.)]\s+", "", stripped))
            continue

        if set(stripped) <= {"-", "*", "_"} and len(stripped) >= 3:
            flush_paragraph()
            flush_bullets()
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(width="100%", color=RULE, thickness=0.5))
            flowables.append(Spacer(1, 4))
            continue

        flush_bullets()
        paragraph.append(stripped)

    flush_paragraph()
    flush_bullets()
    return flowables


# -- Score bar ---------------------------------------------------------------


class ScoreBar(Flowable):
    """A labelled 0-10 bar, drawn rather than tabulated."""

    def __init__(self, label: str, value: float, width: float = 150 * mm) -> None:
        super().__init__()
        self.label = winansi(label)
        self.value = max(0.0, min(10.0, value))
        self.width = width
        self.height = 13

    def draw(self) -> None:
        canvas = self.canv
        label_w = 46 * mm
        bar_x = label_w + 4
        bar_w = self.width - bar_x - 16 * mm

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(MUTED)
        canvas.drawString(0, 3.5, self.label)

        canvas.setFillColor(colors.HexColor("#ececec"))
        canvas.roundRect(bar_x, 3, bar_w, 5, 2.5, stroke=0, fill=1)

        filled = bar_w * (self.value / 10.0)
        if filled > 0:
            canvas.setFillColor(_score_colour(self.value))
            canvas.roundRect(bar_x, 3, max(filled, 5), 5, 2.5, stroke=0, fill=1)

        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(INK)
        canvas.drawRightString(self.width, 3.5, f"{self.value:.1f}")


# -- Document ----------------------------------------------------------------


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ArgusTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            alignment=0,
            textColor=INK,
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "ArgusMeta", parent=base["Normal"], fontSize=8.5, leading=12, textColor=FAINT
        ),
        "h2": ParagraphStyle(
            "ArgusH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceBefore=16,
            spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "ArgusH3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "ArgusBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.7,
            leading=14.5,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "verdict": ParagraphStyle(
            "ArgusVerdict",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "ArgusLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=FAINT,
            spaceAfter=3,
        ),
    }


def _chrome(canvas, doc) -> None:
    """Footer rule, attribution and page number on every page."""
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(FAINT)
    canvas.drawString(20 * mm, 10.5 * mm, "Generated by Argus — argus-research-system")
    canvas.drawRightString(A4[0] - 20 * mm, 10.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(result: dict[str, Any], *, include_appendix: bool = True) -> bytes:
    """Render a run into PDF bytes.

    ``include_appendix`` adds the critique, fact check and source list after the
    report itself.
    """
    styles = _styles()
    buffer = BytesIO()
    topic = (result.get("topic") or "Research report").strip()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=topic,
        author="Argus",
        subject="Multi-agent research report",
    )

    story: list[Flowable] = [Paragraph(html.escape(winansi(topic), quote=False), styles["title"])]

    scores = result.get("scores") or {}
    meta_bits = [datetime.now(UTC).strftime("%d %B %Y")]
    if result.get("model_label"):
        meta_bits.append(str(result["model_label"]))
    sources = result.get("sources") or []
    pages = result.get("pages") or []
    if sources:
        read = sum(1 for page in pages if not page.get("error"))
        meta_bits.append(f"{len(sources)} sources, {read} read in full")
    if result.get("total_ms"):
        meta_bits.append(f"{result['total_ms'] / 1000:.0f}s")

    story.append(
        Paragraph(" &nbsp;·&nbsp; ".join(html.escape(b) for b in meta_bits), styles["meta"])
    )
    story.append(Spacer(1, 7))
    story.append(HRFlowable(width="100%", color=RULE, thickness=0.6))
    story.append(Spacer(1, 10))

    if scores.get("overall") is not None:
        story.append(Paragraph("CRITIC ASSESSMENT", styles["label"]))
        story.append(ScoreBar("Overall", float(scores["overall"]), doc.width))
        story.append(Spacer(1, 3))
        if scores.get("verdict"):
            story.append(Paragraph(html.escape(winansi(str(scores["verdict"]))), styles["verdict"]))
        if scores.get("recommendation"):
            story.append(
                Paragraph(
                    f'<font color="#{_score_colour(float(scores["overall"])).hexval()[2:]}">'
                    f"<b>{html.escape(str(scores['recommendation']))}</b></font>",
                    styles["meta"],
                )
            )
        story.append(Spacer(1, 12))

    story.extend(_markdown_flowables(result.get("report") or "", styles))

    if include_appendix:
        categories = scores.get("categories") or {}
        critic = (result.get("critic") or "").strip()
        factcheck = (result.get("factcheck") or "").strip()

        if categories or critic or factcheck or sources:
            story.append(PageBreak())
            story.append(Paragraph("Appendix", styles["title"]))
            story.append(Spacer(1, 8))

        if categories:
            story.append(Paragraph("Category scores", styles["h2"]))
            for name in CATEGORY_ORDER:
                if name in categories:
                    story.append(ScoreBar(name, float(categories[name]), doc.width))
            story.append(Spacer(1, 8))

        if critic:
            story.append(Paragraph("Critique", styles["h2"]))
            story.extend(_markdown_flowables(_strip_scores(critic), styles))

        if factcheck:
            story.append(Paragraph("Fact check", styles["h2"]))
            story.extend(_markdown_flowables(_strip_scores(factcheck), styles))

        if sources:
            story.append(Paragraph("Sources", styles["h2"]))
            read_urls = {p.get("source_url") or p.get("url") for p in pages if not p.get("error")}
            items = []
            for source in sources:
                url = source.get("url", "")
                suffix = " — read in full" if url in read_urls else ""
                items.append(
                    ListItem(
                        Paragraph(
                            f'<link href="{html.escape(url, quote=True)}" color="#1f4fd8">'
                            f"{html.escape(winansi(source.get('title') or url))}</link>"
                            f'<br/><font size="8" color="#8a8a8a">{html.escape(url)}'
                            f"{suffix}</font>",
                            styles["body"],
                        ),
                        leftIndent=12,
                    )
                )
            story.append(
                ListFlowable(
                    items, bulletType="bullet", bulletFontSize=8, bulletColor=FAINT, leftIndent=14
                )
            )

    doc.build(story, onFirstPage=_chrome, onLaterPages=_chrome)
    return buffer.getvalue()


_SCORE_LINE = re.compile(
    r"^\s*[-*]?\s*(Overall Score|Fact Check Score|Category Scores|Factual Accuracy|"
    r"Depth of Analysis|Structure (?:&|and) Clarity|Use of Sources|Completeness|"
    r"Professional Quality)\s*:.*$",
    re.I | re.M,
)


def _strip_scores(text: str) -> str:
    """Drop lines already drawn as bars, so the appendix does not repeat them."""
    return re.sub(r"\n{3,}", "\n\n", _SCORE_LINE.sub("", text)).strip()
