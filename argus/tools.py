"""Agent tools: web search and a hardened URL reader.

The reader is the only place in ARGUS where a language model chooses a network
destination, so it is treated as untrusted input and guarded accordingly.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from argus.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "ARGUS-Research/2.0 (+https://github.com/SatyamKamboj10011/argus-research-system)"
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443, 8080, 8443}
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml", "text/plain", "application/xml")
MAX_REDIRECTS = 3
MIN_USEFUL_CHARS = 200
"""Below this, a fetch succeeded but produced nothing worth handing to a model -
almost always a client-rendered page or an interstitial."""


class EmptyPageError(ValueError):
    """The page was fetched but carried no usable text."""


class UnsafeURLError(ValueError):
    """The URL points somewhere a public web scraper must not go."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float = 0.0
    domain: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# -- URL safety --------------------------------------------------------------


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def assert_url_is_safe(url: str) -> str:
    """Validate a model-chosen URL before any request is made.

    Blocks non-HTTP schemes, odd ports, and any host that resolves to a private,
    loopback, link-local or reserved address. Without this, a prompt-injected page
    could steer the reader agent at http://169.254.169.254/ and pull cloud instance
    credentials into the report.
    """
    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Blocked scheme {parsed.scheme!r}; only http/https are allowed.")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host.")

    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid port in URL: {exc}") from exc

    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f"Blocked non-standard port {port}.")

    lowered = host.lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        raise UnsafeURLError(f"Blocked internal host {host!r}.")

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host {host!r}: {exc}") from exc

    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeURLError(f"Host {host!r} resolves to non-public address {ip}.")

    return urlunparse(parsed)


def _extract_text(html: str) -> tuple[str, str]:
    """Return (title, text) with page chrome and boilerplate stripped."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe", "svg"]
    ):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text(separator="\n").splitlines()]
    text = "\n".join(ln for ln in lines if len(ln) > 1)
    return title, text


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=3),
    reraise=True,
)
def _fetch(url: str) -> requests.Response:
    return requests.get(
        url,
        timeout=settings.scrape_timeout_seconds,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        allow_redirects=False,
        stream=True,
    )


def fetch_page(url: str) -> dict:
    """Fetch and clean a single page. Every redirect hop is re-validated."""
    current = assert_url_is_safe(url)

    for _ in range(MAX_REDIRECTS + 1):
        resp = _fetch(current)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise UnsafeURLError("Redirect without a Location header.")
            current = assert_url_is_safe(urljoin(current, location))
            continue
        break
    else:
        raise UnsafeURLError("Too many redirects.")

    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    if content_type and not any(ct in content_type for ct in ALLOWED_CONTENT_TYPES):
        resp.close()
        raise ValueError(f"Unsupported content type {content_type!r}.")

    # Cap the download so a huge or endless response cannot exhaust memory.
    chunks, total = [], 0
    for chunk in resp.iter_content(chunk_size=16_384):
        chunks.append(chunk)
        total += len(chunk)
        if total >= settings.scrape_max_bytes:
            break
    resp.close()

    html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    title, text = _extract_text(html)

    # A page that yields no text must not be counted as read. Reporting it as a
    # success would inflate the source count and mislead the reader about how much
    # of the report is actually grounded in full text.
    if len(text.strip()) < MIN_USEFUL_CHARS:
        raise EmptyPageError("No readable text found; the page is probably rendered client-side.")

    return {
        "url": current,
        "title": title,
        "text": text[: settings.scrape_max_chars],
        "chars": len(text),
        "truncated": len(text) > settings.scrape_max_chars,
    }


# -- Search ------------------------------------------------------------------


def search_web(query: str, max_results: int | None = None) -> list[SearchResult]:
    """Structured Tavily search. Raises on misconfiguration rather than returning prose."""
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured on the server.")

    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)
    raw = client.search(
        query=query,
        max_results=max_results or settings.search_max_results,
        search_depth="advanced",
    )
    results = []
    for item in raw.get("results", []):
        url = item.get("url", "")
        results.append(
            SearchResult(
                title=item.get("title", "Untitled"),
                url=url,
                snippet=(item.get("content") or "")[:400],
                score=float(item.get("score") or 0.0),
                domain=urlparse(url).netloc,
            )
        )
    return results


def format_results(results: list[SearchResult]) -> str:
    """Render search results in the shape the agents are prompted to read."""
    return "\n-----\n".join(
        f"Title: {r.title}\nURL: {r.url}\nSnippet: {r.snippet}" for r in results
    )


# -- LangChain tool surface --------------------------------------------------


@tool
def web_search(query: str) -> str:
    """Search the web for recent, reliable information. Returns titles, URLs and snippets."""
    try:
        return format_results(search_web(query)) or "No results found."
    except Exception as exc:  # surfaced to the agent, not to the user
        logger.warning("web_search failed: %s", exc)
        return f"Search failed: {exc}"


@tool
def scrape_url(url: str) -> str:
    """Read a web page and return its main text content. Use on URLs from search results."""
    try:
        page = fetch_page(url)
        return f"# {page['title']}\nSource: {page['url']}\n\n{page['text']}"
    except UnsafeURLError as exc:
        logger.warning("Blocked unsafe scrape target %s: %s", url, exc)
        return f"Refused to fetch that URL: {exc}"
    except EmptyPageError as exc:
        return f"That page carried no readable text: {exc}"
    except Exception as exc:
        logger.warning("scrape_url failed for %s: %s", url, exc)
        return f"Could not read that page: {exc}"
