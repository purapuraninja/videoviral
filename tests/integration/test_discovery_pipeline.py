"""End-to-end discovery pipeline on SQLite (no wigolo/postgres required).

Proves the Phase-1 happy path with the mock client, and — using a stub client that
returns realistic multi-story results — that the pipeline groups by story, caps at
five candidates, and survives a failing/degraded wigolo.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from vvf_database.base import Base
from vvf_database import models  # noqa: F401
from vvf_database.models import (
    ContentCandidate,
    ResearchQuery,
    ResearchRun,
    SourceDocument,
    User,
)
from vvf_database.session import get_session_factory
from vvf_discovery_worker.pipeline import run_discovery
from vvf_wigolo import MockWigoloClient, WigoloSearchHit, WigoloSearchResult


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def _make_run(db: Session, keyword: str = "gempa bali") -> ResearchRun:
    user = User(username=f"admin-{keyword}", password_hash="x", is_admin=True)
    db.add(user)
    db.flush()
    run = ResearchRun(
        keyword=keyword,
        research_prompt="",
        language="id-ID",
        period_days=7,
        created_by=user.id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_discovery_pipeline_persists_candidates():
    db = _make_session()
    run = _make_run(db)

    candidates = run_discovery(run, db, MockWigoloClient())

    # The mock returns 3 hits about one story -> at least 1, at most 5.
    assert 1 <= len(candidates) <= 5
    for c in candidates:
        assert c.status == "proposed"
        assert c.title
        assert c.final_score >= 0.0
    # Source documents must have been persisted.
    src_count = db.query(SourceDocument).filter_by(research_run_id=run.id).count()
    assert src_count >= len(candidates)
    # The run is marked completed.
    db.refresh(run)
    assert run.status == "completed"
    db.close()


class _MultiStoryClient:
    """Stub returning several distinct stories, like real wigolo output."""

    def __init__(self, degraded: list[str] | None = None) -> None:
        self.calls: list[object] = []
        self._degraded = degraded or []

    def search(self, query, *, language="id-ID", limit=20, **_kw):
        self.calls.append(query)
        hits = [
            WigoloSearchHit(
                title="Gempa M5.2 guncang Bali",
                url="https://a.id/gempa-bali",
                snippet="Gempa bermagnitudo 5,2 mengguncang Bali.",
                publisher="A News",
                published_at="2026-07-29T09:00:00Z",
                score=0.95,
            ),
            WigoloSearchHit(
                title="Gempa Bali magnitudo 5,2 kedalaman 10 km",
                url="https://b.id/bmkg-gempa",
                snippet="BMKG mencatat gempa dangkal di selatan Bali.",
                publisher="B News",
                published_at="2026-07-29T09:10:00Z",
                score=0.9,
            ),
            WigoloSearchHit(
                title="Banjir melanda Jakarta Selatan",
                url="https://a.id/banjir-jakarta",
                snippet="Hujan deras menyebabkan banjir di Jakarta Selatan.",
                publisher="A News",
                published_at="2026-07-29T08:00:00Z",
                score=0.8,
            ),
            WigoloSearchHit(
                title="Timnas menang lawan Vietnam",
                url="https://c.id/timnas",
                snippet="Timnas Indonesia menang 2-0.",
                publisher="C Sport",
                published_at="2026-07-29T07:00:00Z",
                score=0.7,
            ),
        ]
        return WigoloSearchResult(
            query=query if isinstance(query, str) else ", ".join(query),
            hits=hits[:limit],
            degraded_backends=self._degraded,
            engines_used=["bing", "duckduckgo"],
        )


def test_pipeline_groups_by_story_not_publisher():
    """Two same-publisher articles about different events stay separate."""
    db = _make_session()
    run = _make_run(db, keyword="berita indonesia")

    candidates = run_discovery(run, db, _MultiStoryClient())

    titles = {c.title for c in candidates}
    # The two Bali earthquake articles merge; Jakarta flood and football do not.
    assert len(candidates) == 3, titles
    assert any("Gempa" in t for t in titles)
    assert any("Banjir" in t for t in titles)
    assert any("Timnas" in t for t in titles)

    # The merged earthquake candidate must cite both of its sources.
    gempa = next(c for c in candidates if "Gempa" in c.title)
    assert len(gempa.source_links) == 2
    db.close()


def test_pipeline_sends_query_variants_as_one_array_call():
    """wigolo fuses variants in one call — a serial loop would be slower."""
    db = _make_session()
    run = _make_run(db, keyword="gempa bali")
    client = _MultiStoryClient()

    run_discovery(run, db, client)

    assert len(client.calls) == 1
    assert isinstance(client.calls[0], list)
    # Every variation is still recorded for provenance.
    assert db.query(ResearchQuery).filter_by(research_run_id=run.id).count() == len(
        client.calls[0]
    )
    db.close()


def test_pipeline_ranks_candidates_and_caps_at_five():
    db = _make_session()
    run = _make_run(db, keyword="banyak berita")

    # Genuinely distinct stories (shared boilerplate would legitimately merge).
    _HEADLINES = [
        "Gempa mengguncang Lombok",
        "Banjir melanda Semarang",
        "Timnas kalahkan Malaysia",
        "Harga cabai melonjak",
        "Gunung Merapi erupsi",
        "Kereta cepat resmi beroperasi",
        "Rupiah menguat signifikan",
        "Vaksin baru disetujui BPOM",
    ]

    class _ManyStories:
        def search(self, query, *, language="id-ID", limit=20, **_kw):
            hits = [
                WigoloSearchHit(
                    title=headline,
                    url=f"https://x.id/{i}",
                    snippet=f"Detail: {headline}.",
                    publisher=f"Outlet {i}",
                    published_at="2026-07-29T09:00:00Z",
                    score=1.0 - i / 100,
                )
                for i, headline in enumerate(_HEADLINES)
            ]
            return WigoloSearchResult(query="q", hits=hits)

    candidates = run_discovery(run, db, _ManyStories())

    assert len(candidates) == 5  # exactly the plan's five best
    ranks = [c.rank for c in candidates]
    assert ranks == [1, 2, 3, 4, 5]
    scores = [c.final_score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    db.close()


def test_pipeline_survives_wigolo_failure():
    """A dead wigolo must not leave the run stuck in 'running'."""
    db = _make_session()
    run = _make_run(db, keyword="apa saja")

    class _Broken:
        def search(self, *_a, **_kw):
            raise RuntimeError("connection refused")

    candidates = run_discovery(run, db, _Broken())

    assert candidates == []
    db.refresh(run)
    assert run.status == "completed"
    # Queries are still recorded, with zero results, so the failure is visible.
    queries = db.query(ResearchQuery).filter_by(research_run_id=run.id).all()
    assert queries and all(q.result_count == 0 for q in queries)
    db.close()


def test_pipeline_completes_with_degraded_backends():
    """Degraded engines reduce the pool but must not fail the run."""
    db = _make_session()
    run = _make_run(db, keyword="gempa")

    candidates = run_discovery(run, db, _MultiStoryClient(degraded=["brave", "startpage"]))

    assert candidates
    db.refresh(run)
    assert run.status == "completed"
    db.close()
