"""GENESIS tool adapters: honest source retrieval and discovery.

  WebFetchTool          — fetch a URL; failure => ok=False, never a fake source.
  FetchResult/require_ok — fetch outcome + strict accessor.
  SemanticScholarBackend — free academic discovery (no key).
  WebSearchBackend       — generic JSON-SERP adapter (provider injected).
  HttpResponse/HttpGet/default_http_get/content_hash — HTTP boundary.
"""

from __future__ import annotations

from .arxiv_backend import ArxivBackend
from .fetch import FetchResult, WebFetchTool, require_ok
from .http import HttpGet, HttpResponse, content_hash, default_http_get
from .search import SemanticScholarBackend, WebSearchBackend

__all__ = [
    "WebFetchTool",
    "FetchResult",
    "require_ok",
    "SemanticScholarBackend",
    "WebSearchBackend",
    "ArxivBackend",
    "HttpResponse",
    "HttpGet",
    "default_http_get",
    "content_hash",
]
