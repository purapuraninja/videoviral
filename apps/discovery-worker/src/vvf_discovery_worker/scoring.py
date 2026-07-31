"""Candidate scoring per IMPLEMENTATION_PLAN.md section 8.

```
final_score = freshness_score * 0.30 + source_score    * 0.30 +
              virality_score  * 0.25 + relevance_score * 0.15 -
              risk_score       * 0.30
```

Scores are produced from raw signals (recency, source quality, snippet
engagement proxies, keyword relevance) plus risk flags. All scores are
clamped to [0, 1] (except final_score which can go negative on high risk).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScoredSignals:
    freshness: float = 0.0
    source: float = 0.0
    virality: float = 0.0
    relevance: float = 0.0
    risk: float = 0.0

    @property
    def final(self) -> float:
        return (
            self.freshness * 0.30
            + self.source * 0.30
            + self.virality * 0.25
            + self.relevance * 0.15
            - self.risk * 0.30
        )


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def freshness_score(published_at: datetime | None, now: datetime | None = None) -> float:
    """Newer is better; decays over a 7-day window."""
    if published_at is None:
        return 0.0
    now = now or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    return _clamp(1.0 - age_hours / (7 * 24))


def relevance_score(text: str, keyword: str) -> float:
    """Simple keyword-overlap relevance proxy (subword matching)."""
    if not text or not keyword:
        return 0.0
    tokens = [t.lower() for t in keyword.split() if t]
    if not tokens:
        return 0.0
    hay = text.lower()
    hits = sum(1 for t in tokens if t in hay)
    return _clamp(hits / len(tokens))


def virality_score(snippet: str, title: str) -> float:
    """Engagement proxy: presence of high-arousal / urgency cues."""
    cues = (
        "viral", "trending", "terkini", "breaking", "urgent", "luar biasa",
        "pecah", "ledakan", "skandal", "heboh", "breaking news",
    )
    text = f"{title} {snippet}".lower()
    return _clamp(0.4 + 0.15 * sum(1 for c in cues if c in text), hi=1.0)


def risk_score(risk_flags: list[str]) -> float:
    """More flags => higher risk; capped at 1.0."""
    if not risk_flags:
        return 0.0
    return _clamp(0.25 * len(risk_flags))


def score_candidate(
    *,
    keyword: str,
    title: str,
    snippet: str,
    published_at: datetime | None,
    source_quality: float | None,
    risk_flags: list[str],
) -> ScoredSignals:
    return ScoredSignals(
        freshness=freshness_score(published_at),
        source=_clamp(source_quality or 0.0),
        virality=virality_score(snippet, title),
        relevance=relevance_score(f"{title} {snippet}", keyword),
        risk=risk_score(risk_flags),
    )
