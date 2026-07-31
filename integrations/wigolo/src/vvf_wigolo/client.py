"""wigolo client.

wigolo is a local-first web search/fetch/crawl/research service exposed via an
MCP HTTP transport. The VPS only ever talks to wigolo through this adapter
(IMPLEMENTATION_PLAN.md §6), never modifying the upstream codebase.

Primary operations mirrored here:
    - search:   execute query variations in parallel
    - fetch:    retrieve selected pages
    - extract:  extract article metadata + structured content
    - cache:    prevent repeated work for the same keyword

The client speaks wigolo's MCP HTTP transport (JSON-RPC ``tools/call``). A
``MockWigoloClient`` is provided so the discovery worker and unit tests never
require a running wigolo instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from vvf_shared.config import get_settings


@dataclass
class WigoloSearchHit:
    """A single search result row returned by wigolo."""

    title: str
    url: str
    snippet: str = ""
    publisher: str | None = None
    published_at: str | None = None
    score: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WigoloSearchResult:
    """Aggregated result of a ``search`` operation."""

    query: str
    hits: list[WigoloSearchHit] = field(default_factory=list)
    degraded_backends: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class WigoloClientProtocol(Protocol):
    def search(self, query: str, *, language: str = "id-ID", limit: int = 20) -> WigoloSearchResult: ...

    def fetch(self, url: str) -> dict[str, Any]: ...

    def extract(self, url: str) -> dict[str, Any]: ...


class WigoloClient:
    """HTTP client for the wigolo MCP transport.

    wigolo exposes its tools over a JSON-RPC 2.0 endpoint. We call ``tools/call``
    with the tool name and arguments. The base URL and optional bearer token come
    from environment (``VVF_WIGOLO_*`` / ``WIGOLO_BASE_URL``).
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.wigolo_base_url).rstrip("/")
        self._token = token or settings.wigolo_api_token
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": tool, "arguments": arguments}}
        resp = self._client.post(self._base_url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"wigolo error: {body['error']}")
        return body.get("result")

    def search(self, query: str, *, language: str = "id-ID", limit: int = 20) -> WigoloSearchResult:
        result = self._call("search", {"query": query, "language": language, "limit": limit})
        hits = [WigoloSearchHit(**h) for h in (result.get("hits") or []) if isinstance(h, dict)]
        return WigoloSearchResult(
            query=query,
            hits=hits,
            degraded_backends=result.get("degraded_backends", []),
            raw=result or {},
        )

    def fetch(self, url: str) -> dict[str, Any]:
        return self._call("fetch", {"url": url}) or {}

    def extract(self, url: str) -> dict[str, Any]:
        return self._call("extract", {"url": url}) or {}


class MockWigoloClient:
    """In-memory wigolo stand-in for tests and local dev without wigolo running.

    Returns deterministic, source-backed hits so candidate scoring can be
    exercised end-to-end. Hit URLs are stable so dedup/canonicalization logic
    can be validated.
    """

    _SAMPLE = [
        WigoloSearchHit(
            title="Gempa M5.2 guncang Bali",
            url="https://example.com/news/bali-gempa-5-2",
            snippet="Gempa bermagnitudo 5,2 mengguncang Bali sore ini. BMKG menyebut tidak berpotensi tsunami.",
            publisher="Berita Update",
            published_at="2026-07-29T09:00:00Z",
            score=0.92,
        ),
        WigoloSearchHit(
            title="BMKG: Gempa Bali 5,2 magnitudo, kedalaman 10 km",
            url="https://example.com/bmkg/bali-gempa-5-2",
            snippet="Badan Meteorologi Klimatologi dan Geofisika mencatat gempa dangkal di selatan Bali.",
            publisher="BMKG Info",
            published_at="2026-07-29T09:10:00Z",
            score=0.9,
        ),
        WigoloSearchHit(
            title="Warga Bali tenang usai guncangan gempa",
            url="https://example.com/warga/bali-tenang-gempa",
            snippet="Warga memilih tetap di rumah usai gempa; tidak ada kerusakan signifikan dilaporkan.",
            publisher="Detik News",
            published_at="2026-07-29T10:00:00Z",
            score=0.81,
        ),
    ]

    def search(self, query: str, *, language: str = "id-ID", limit: int = 20) -> WigoloSearchResult:
        return WigoloSearchResult(
            query=query, hits=list(self._SAMPLE[:limit]), raw={"mock": True}
        )

    def fetch(self, url: str) -> dict[str, Any]:
        return {"url": url, "content": "<html>mock page</html>", "mock": True}

    def extract(self, url: str) -> dict[str, Any]:
        return {
            "url": url,
            "title": "Mock article",
            "publisher": "Mock Publisher",
            "published_at": "2026-07-29T00:00:00Z",
            "content": "Mock article body text.",
            "mock": True,
        }
