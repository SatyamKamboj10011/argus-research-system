"""Tests for the agent tools, with an emphasis on the URL safety guard."""

from __future__ import annotations

import pytest
import requests

from argus.tools import (
    MIN_USEFUL_CHARS,
    EmptyPageError,
    SearchResult,
    UnsafeURLError,
    _extract_text,
    assert_url_is_safe,
    fetch_page,
    format_results,
)

BLOCKED = [
    pytest.param("http://169.254.169.254/latest/meta-data/", id="aws-imds"),
    pytest.param("http://127.0.0.1/admin", id="loopback"),
    pytest.param("http://[::1]/", id="loopback-v6"),
    pytest.param("http://10.0.0.5/internal", id="private-10"),
    pytest.param("http://192.168.1.1/", id="private-192"),
    pytest.param("http://172.16.4.2/", id="private-172"),
    pytest.param("file:///etc/passwd", id="file-scheme"),
    pytest.param("gopher://example.com/", id="gopher-scheme"),
    pytest.param("http://localhost/", id="localhost"),
    pytest.param("http://printer.local/", id="mdns"),
    pytest.param("https://example.com:22/", id="ssh-port"),
    pytest.param("https://example.com:6379/", id="redis-port"),
    pytest.param("http://0.0.0.0/", id="unspecified"),
    pytest.param("not-a-url", id="garbage"),
]


@pytest.mark.parametrize("url", BLOCKED)
def test_unsafe_urls_are_blocked(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        assert_url_is_safe(url)


@pytest.mark.parametrize("url", ["https://example.com/article", "http://example.com:80/x?y=1"])
def test_public_urls_are_allowed(url: str) -> None:
    assert assert_url_is_safe(url).startswith("http")


def test_extract_text_strips_chrome_and_keeps_article() -> None:
    html = """
    <html><head><title>Rare Earths</title></head>
    <body>
      <nav>Home About Contact</nav>
      <script>window.track()</script>
      <article><p>China refines most of the world's rare earths.</p>
      <p>Supply is concentrated.</p></article>
      <footer>Copyright 2026</footer>
    </body></html>
    """
    title, text = _extract_text(html)
    assert title == "Rare Earths"
    assert "China refines" in text
    assert "Home About Contact" not in text
    assert "window.track" not in text
    assert "Copyright" not in text


def test_extract_text_handles_empty_document() -> None:
    title, text = _extract_text("")
    assert title == ""
    assert text == ""


def test_format_results_shape_matches_agent_prompt() -> None:
    out = format_results(
        [SearchResult(title="T", url="https://a.com/x", snippet="S", domain="a.com")]
    )
    assert "Title: T" in out
    assert "URL: https://a.com/x" in out
    assert "Snippet: S" in out


def test_extract_text_of_a_client_rendered_shell_is_empty() -> None:
    """A JS-rendered page has a body but no prose worth reading."""
    html = "<html><head><title>App</title></head><body><div id='root'></div></body></html>"
    _title, text = _extract_text(html)
    assert len(text.strip()) < MIN_USEFUL_CHARS


def test_fetch_page_rejects_a_page_with_no_readable_text(monkeypatch) -> None:
    """Counting a text-less page as read would inflate the source count."""
    monkeypatch.setattr("argus.tools.assert_url_is_safe", lambda url: url)
    monkeypatch.setattr(
        "argus.tools._fetch", lambda url: _FakeResponse("<html><body></body></html>")
    )

    with pytest.raises(EmptyPageError):
        fetch_page("https://example.com/spa")


def test_fetch_page_returns_a_substantial_page(monkeypatch) -> None:
    body = "Refining capacity is concentrated in a handful of countries. " * 12
    monkeypatch.setattr("argus.tools.assert_url_is_safe", lambda url: url)
    monkeypatch.setattr(
        "argus.tools._fetch",
        lambda url: _FakeResponse(
            f"<html><head><title>T</title></head><body><article><p>{body}</p></article></body></html>"
        ),
    )

    page = fetch_page("https://example.com/article")
    assert page["title"] == "T"
    assert page["chars"] >= MIN_USEFUL_CHARS
    assert "Refining capacity" in page["text"]


class _FakeResponse:
    """The slice of requests.Response that fetch_page actually touches."""

    def __init__(self, html: str, status: int = 200) -> None:
        self._body = html.encode()
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"

    def iter_content(self, chunk_size: int = 16384):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start : start + chunk_size]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def close(self) -> None:
        return None
