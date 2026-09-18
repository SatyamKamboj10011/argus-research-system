"""Backwards-compatible shim. Use :mod:`argus.tools`."""

from argus.tools import fetch_page, format_results, scrape_url, search_web, web_search

__all__ = ["web_search", "scrape_url", "search_web", "fetch_page", "format_results"]
