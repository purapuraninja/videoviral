"""wigolo client.

wigolo is a local-first web search/fetch/crawl/extract service. The VPS only ever
talks to it through this adapter (IMPLEMENTATION_PLAN.md §6); the upstream
codebase (AGPL-3.0) is never modified.

Transport: wigolo's **REST API** (``wigolo serve``), which exposes one route per
tool at ``POST /v1/{tool}`` plus an always-open ``GET /health``. This is simpler
and more stable than driving the MCP JSON-RPC transport, and it is the documented
surface for non-MCP callers.

Operations used by the discovery pipeline:
    - search:   multi-engine search; a query **array** runs variants in parallel
    - fetch:    retrieve one page as clean markdown
    - extract:  structured metadata for a page
    - cache:    query pages wigolo has already seen (free, instant)

Search is keyless. An LLM is only needed for ``research``/``agent`` synthesis,
which this pipeline deliberately does not use — we keep raw, source-backed
evidence instead of an LLM summary.

A ``MockWigoloClient`` is provided so unit tests and local dev never require a
running wigolo instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from vvf_shared.config import get_settings

# wigolo caps `max_results` at 20 and a query array at 10 variants.
_MAX_RESULTS = 20


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
    engines_used: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class WigoloClientProtocol(Protocol):
    def search(
        self, query: str | list[str], *, language: str = "id-ID", limit: int = 20
    ) -> WigoloSearchResult: ...

    def fetch(self, url: str) -> dict[str, Any]: ...

    def extract(self, url: str) -> dict[str, Any]: ...

    def health(self) -> dict[str, Any]: ...


def _publisher_from(result: dict[str, Any], url: str) -> str | None:
    """Best-effort publisher name: explicit field, else the registrable domain."""
    for key in ("publisher", "site_name", "source"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    meta = result.get("metadata")
    if isinstance(meta, dict):
        for key in ("publisher", "site_name", "og:site_name"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    from urllib.parse import urlparse

    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    return host or None


def _published_at_from(result: dict[str, Any]) -> str | None:
    """Prefer wigolo's freshness signal, then common date fields."""
    fresh = result.get("freshness_signal")
    if isinstance(fresh, dict):
        for key in ("published_date", "published"):
            value = fresh.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("published_at", "published_date", "date"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    meta = result.get("metadata")
    if isinstance(meta, dict):
        for key in ("published_time", "article:published_time", "date"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _score_from(result: dict[str, Any]) -> float | None:
    """Use wigolo's explainable evidence score, falling back to relevance."""
    evidence = result.get("evidence_score")
    if isinstance(evidence, dict):
        final = evidence.get("final")
        if isinstance(final, (int, float)):
            return float(final)
    for key in ("relevance_score", "score"):
        value = result.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _snippet_from(result: dict[str, Any]) -> str:
    """Prefer a verbatim excerpt (byte-pinned evidence) over the snippet."""
    for key in ("excerpt", "snippet", "description", "content"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def hit_from_result(result: dict[str, Any]) -> WigoloSearchHit | None:
    """Map one wigolo search result into a :class:`WigoloSearchHit`."""
    url = result.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    return WigoloSearchHit(
        title=(result.get("title") or "").strip() or url,
        url=url.strip(),
        snippet=_snippet_from(result),
        publisher=_publisher_from(result, url),
        published_at=_published_at_from(result),
        score=_score_from(result),
        raw=result,
    )


class WigoloError(RuntimeError):
    """wigolo returned an error response."""


class WigoloClient:
    """REST client for a ``wigolo serve`` daemon.

    Base URL and bearer token come from settings (``VVF_WIGOLO_BASE_URL`` /
    ``VVF_WIGOLO_API_TOKEN``). A token is mandatory whenever wigolo is bound off
    loopback, which is how we run it in Docker.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.wigolo_base_url).rstrip("/")
        self._token = token or settings.wigolo_api_token
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _call(self, tool: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        """POST to ``/v1/{tool}``, raising :class:`WigoloError` on failure."""
        try:
            resp = self._client.post(
                f"{self._base_url}/v1/{tool}",
                json=payload,
                headers=self._headers(),
                timeout=timeout or self._timeout,
            )
        except httpx.HTTPError as exc:
            raise WigoloError(f"{tool} request failed: {exc}") from exc
        if resp.status_code >= 400:
            # wigolo returns {error, error_reason, hint} on failures.
            detail = resp.text[:300].replace("\n", " ")
            raise WigoloError(f"{tool} HTTP {resp.status_code}: {detail}")
        body = resp.json()
        if not isinstance(body, dict):
            raise WigoloError(f"{tool} returned a non-object body")
        return body

    def health(self) -> dict[str, Any]:
        """Liveness + component status. Always open (no token required)."""
        try:
            resp = self._client.get(f"{self._base_url}/health", timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WigoloError(f"health check failed: {exc}") from exc

    def search(
        self,
        query: str | list[str],
        *,
        language: str = "id-ID",
        limit: int = 20,
        category: str = "news",
        time_range: str | None = "week",
        search_depth: str = "balanced",
    ) -> WigoloSearchResult:
        """Run a search (or several variants in parallel when ``query`` is a list).

        Defaults target the pipeline's use case: recent news in the run's
        language. ``category="news"`` makes wigolo's date handling date-aware, and
        ``time_range`` keeps stale articles out of the candidate pool.
        """
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max(1, min(limit, _MAX_RESULTS)),
            "search_depth": search_depth,
            # Advisory hints; wigolo also infers language from the query.
            "language": (language or "").split("-")[0] or "id",
        }
        if category:
            payload["category"] = category
        if time_range:
            payload["time_range"] = time_range

        body = self._call("search", payload)
        results = body.get("results")
        hits: list[WigoloSearchHit] = []
        for row in results if isinstance(results, list) else []:
            if isinstance(row, dict) and (hit := hit_from_result(row)) is not None:
                hits.append(hit)

        warnings = body.get("engine_warnings")
        degraded: list[str] = []
        if isinstance(warnings, list):
            degraded = [str(w) for w in warnings]
        elif isinstance(warnings, dict):
            degraded = [str(k) for k in warnings]
        # Engine telemetry also reports per-engine outcomes.
        telemetry = body.get("engine_telemetry")
        if isinstance(telemetry, list):
            degraded += [
                str(t.get("name"))
                for t in telemetry
                if isinstance(t, dict) and t.get("outcome") not in (None, "ok", "success")
            ]

        engines = body.get("engines_used")
        return WigoloSearchResult(
            query=query if isinstance(query, str) else ", ".join(query),
            hits=hits,
            degraded_backends=sorted(set(degraded)),
            engines_used=[str(e) for e in engines] if isinstance(engines, list) else [],
            raw=body,
        )

    def fetch(self, url: str, *, max_content_chars: int = 8000) -> dict[str, Any]:
        """Fetch one page as clean markdown."""
        return self._call("fetch", {"url": url, "max_content_chars": max_content_chars})

    def extract(self, url: str, *, mode: str = "metadata") -> dict[str, Any]:
        """Extract structured data from a page (metadata by default)."""
        return self._call("extract", {"url": url, "mode": mode})

    def cache(self, query: str, *, limit: int = 20, mode: str = "fts") -> dict[str, Any]:
        """Query pages wigolo has already seen — instant and free."""
        return self._call("cache", {"query": query, "limit": limit, "mode": mode})

    def close(self) -> None:
        self._client.close()


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

    def search(
        self, query: str | list[str], *, language: str = "id-ID", limit: int = 20, **_kw: Any
    ) -> WigoloSearchResult:
        return WigoloSearchResult(
            query=query if isinstance(query, str) else ", ".join(query),
            hits=list(self._SAMPLE[:limit]),
            raw={"mock": True},
        )

    def fetch(self, url: str, **_kw: Any) -> dict[str, Any]:
        return {"url": url, "markdown": "mock page", "mock": True}

    def extract(self, url: str, **_kw: Any) -> dict[str, Any]:
        return {
            "url": url,
            "title": "Mock article",
            "publisher": "Mock Publisher",
            "published_at": "2026-07-29T00:00:00Z",
            "content": "Mock article body text.",
            "mock": True,
        }

    def cache(self, query: str, **_kw: Any) -> dict[str, Any]:
        return {"results": [], "mock": True}

    def health(self) -> dict[str, Any]:
        return {"status": "healthy", "mock": True}

    def close(self) -> None:
        return None
