"""wigolo REST client: response mapping, degraded-backend reporting, errors.

These tests drive the client against a stubbed transport — no wigolo daemon and
no network. They pin the shape of wigolo's real ``/v1/search`` response so a
schema change surfaces here rather than in production.
"""

from __future__ import annotations

import httpx
import pytest
from vvf_wigolo import WigoloClient, WigoloError, hit_from_result

# Abridged but faithful shape of a real wigolo /v1/search response.
_REAL_RESPONSE = {
    "results": [
        {
            "title": "Gempa M5.2 guncang Bali",
            "url": "https://news.example.id/bali-gempa?utm_source=x",
            "snippet": "Gempa bermagnitudo 5,2 mengguncang Bali sore ini.",
            "excerpt": "BMKG menyebut gempa tidak berpotensi tsunami.",
            "relevance_score": 0.968,
            "evidence_score": {
                "final": 0.86,
                "components": {"base_rrf": 0.023, "domain_quality": 1, "engine_consensus": 3},
                "explanation": "strong lexical alignment",
            },
            "freshness_signal": {"published_date": "2026-07-29", "confidence": "high"},
        },
        {
            "title": "BMKG catat gempa dangkal di selatan Bali",
            "url": "https://bmkg.example.id/gempa/bali",
            "snippet": "Kedalaman 10 km, tidak berpotensi tsunami.",
            "relevance_score": 0.91,
            "publisher": "BMKG",
        },
        # Rows without a URL are unusable and must be dropped.
        {"title": "no url here", "snippet": "..."},
    ],
    "engines_used": ["bing", "duckduckgo"],
    "engine_telemetry": [
        {"name": "bing", "latency_ms": 420, "outcome": "ok"},
        {"name": "brave", "latency_ms": 0, "outcome": "error"},
    ],
    "engine_warnings": ["startpage rate-limited"],
}


def _client(handler) -> WigoloClient:
    """A WigoloClient whose HTTP calls are served by ``handler``."""
    client = WigoloClient(base_url="http://wigolo.test:3333", token="tok")
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


# --- result mapping --------------------------------------------------------


def test_hit_from_result_prefers_excerpt_and_evidence_score():
    hit = hit_from_result(_REAL_RESPONSE["results"][0])
    assert hit is not None
    # A verbatim excerpt is better evidence than the snippet.
    assert hit.snippet == "BMKG menyebut gempa tidak berpotensi tsunami."
    # wigolo's explainable evidence score wins over relevance_score.
    assert hit.score == 0.86
    assert hit.published_at == "2026-07-29"


def test_hit_from_result_derives_publisher_from_host():
    hit = hit_from_result(_REAL_RESPONSE["results"][0])
    assert hit is not None
    assert hit.publisher == "news.example.id"


def test_hit_from_result_uses_explicit_publisher_when_present():
    hit = hit_from_result(_REAL_RESPONSE["results"][1])
    assert hit is not None
    assert hit.publisher == "BMKG"
    # No evidence_score -> fall back to relevance_score.
    assert hit.score == 0.91


def test_hit_from_result_rejects_rows_without_url():
    assert hit_from_result({"title": "x", "snippet": "y"}) is None


def test_search_maps_results_and_reports_degraded_engines():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_REAL_RESPONSE)

    result = _client(handler).search("gempa bali", language="id-ID", limit=5)

    assert seen["url"] == "http://wigolo.test:3333/v1/search"
    assert seen["auth"] == "Bearer tok"
    # The unusable row is dropped, the two real ones kept.
    assert len(result.hits) == 2
    assert result.engines_used == ["bing", "duckduckgo"]
    # Both the warning and the failed engine are surfaced, never hidden.
    assert "brave" in result.degraded_backends
    assert "startpage rate-limited" in result.degraded_backends


def test_search_sends_array_for_parallel_variants():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": []})

    _client(handler).search(["a", "b", "c"], language="id-ID")
    body = captured["body"]
    assert body["query"] == ["a", "b", "c"]  # parallel breadth in one call
    assert body["category"] == "news"
    assert body["time_range"] == "week"
    assert body["language"] == "id"  # advisory hint, not the full BCP-47 tag


def test_search_clamps_limit_to_wigolo_maximum():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": []})

    _client(handler).search("q", limit=500)
    assert captured["body"]["max_results"] == 20


# --- error handling --------------------------------------------------------


def test_search_raises_wigolo_error_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": "unauthorized", "error_reason": "unauthorized"}
        )

    with pytest.raises(WigoloError, match="401"):
        _client(handler).search("q")


def test_search_raises_wigolo_error_on_transport_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(WigoloError, match="failed"):
        _client(handler).search("q")


def test_health_is_unauthenticated_and_returns_status():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "healthy", "browsers": "ready"})

    assert _client(handler).health()["status"] == "healthy"


def test_health_raises_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with pytest.raises(WigoloError):
        _client(handler).health()


def test_missing_results_key_yields_no_hits():
    """A degraded response must not crash the pipeline."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"warning": "all engines failed"})

    result = _client(handler).search("q")
    assert result.hits == []
