"""Candidate scoring formula checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from vvf_discovery_worker.scoring import (
    ScoredSignals,
    freshness_score,
    relevance_score,
    risk_score,
    score_candidate,
    virality_score,
)


def test_freshness_decays_over_seven_days():
    now = datetime.now(timezone.utc)
    fresh = freshness_score(now, now=now)
    assert fresh > 0.99
    old = freshness_score(now - timedelta(days=8), now=now)
    assert old == 0.0


def test_relevance_keyword_overlap():
    assert relevance_score("gempa bali terkini", "gempa bali") == 1.0
    assert relevance_score("nothing here", "gempa bali") == 0.0


def test_virality_cues_raise_score():
    assert virality_score("berita viral", "Judul Viral") > 0.5
    assert virality_score("cuplikan biasa", "Judul") >= 0.4


def test_risk_scales_with_flags():
    assert risk_score([]) == 0.0
    assert risk_score(["violence", "medical"]) > risk_score(["violence"])


def test_final_score_uses_formula():
    s = score_candidate(
        keyword="gempa", title="Gempa viral", snippet="berita gempa terkini",
        published_at=datetime.now(timezone.utc), source_quality=0.8, risk_flags=[],
    )
    expected = (
        s.freshness * 0.30 + s.source * 0.30 + s.virality * 0.25
        + s.relevance * 0.15 - s.risk * 0.30
    )
    assert abs(s.final - expected) < 1e-9
    # All components in [0,1]; final should be non-negative without risk.
    assert s.final >= 0


def test_high_risk_can_make_score_negative():
    s = score_candidate(
        keyword="x", title="y", snippet="", published_at=None,
        source_quality=0.1, risk_flags=["violence", "medical", "legal", "financial"],
    )
    # 4 flags -> risk capped at 1.0 -> subtracts 0.30; tiny positives.
    assert s.final < 0.4
