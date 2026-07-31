"""wigolo mapper: URL canonicalization + dedup normalization."""

from __future__ import annotations

from datetime import datetime, timezone

from vvf_wigolo import MockWigoloClient, canonicalize_url, normalize_search_results


def test_canonicalize_strips_tracking_and_fragment():
    url = "https://Example.com/news/x?utm_source=twitter&fbclid=abc#main"
    assert canonicalize_url(url) == "https://example.com/news/x"


def test_canonicalize_adds_scheme():
    assert canonicalize_url("example.com/p") == "https://example.com/p"


def test_normalize_dedups_by_canonical_url():
    client = MockWigoloClient()
    result = client.search("gempa bali", language="id-ID")
    sources = normalize_search_results(result, fetched_at=datetime.now(timezone.utc))
    # All sample URLs are distinct, so no dedup expected here, but the count
    # must equal the hit count and every canonical URL must be unique.
    assert len(sources) == len(result.hits)
    canon = [s.canonical_url for s in sources]
    assert len(set(canon)) == len(canon)
    # content hashes should be populated and unique.
    hashes = [s.content_hash for s in sources if s.content_hash]
    assert len(set(hashes)) == len(hashes)


def test_normalize_dedups_identical_urls():
    from vvf_wigolo import WigoloSearchHit, WigoloSearchResult

    hits = [
        WigoloSearchHit(title="A", url="https://x.com/a", snippet="s1", score=0.5),
        WigoloSearchHit(title="A2", url="https://x.com/a?utm_source=z", snippet="s2", score=0.9),
    ]
    result = WigoloSearchResult(query="q", hits=hits)
    sources = normalize_search_results(result)
    assert len(sources) == 1
    # The higher-quality variant should win.
    assert sources[0].source_quality_score == 0.9
