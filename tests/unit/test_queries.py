"""Query variation generation."""

from __future__ import annotations

from vvf_discovery_worker.queries import build_query_variations


def test_three_to_eight_variations():
    vs = build_query_variations("gempa bali")
    assert 3 <= len(vs) <= 8
    assert all("gempa bali" in v for v in vs)


def test_prompt_adds_variation():
    vs_no = build_query_variations("banjir", "")
    vs = build_query_variations("banjir", "fokus jakarta")
    assert len(vs) >= len(vs_no)


def test_empty_keyword_returns_empty():
    assert build_query_variations("") == []
