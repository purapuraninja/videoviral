"""End-to-end discovery pipeline on SQLite (no wigolo/postgres required).

Proves the Phase-1 happy path: create a research run, run discovery with the
MockWigoloClient, and confirm up to five source-backed candidates are persisted.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from vvf_database.base import Base
from vvf_database import models  # noqa: F401
from vvf_database.models import ContentCandidate, ResearchRun, User, SourceDocument
from vvf_database.session import get_session_factory
from vvf_discovery_worker.pipeline import run_discovery
from vvf_wigolo import MockWigoloClient


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_discovery_pipeline_persists_candidates():
    db = _make_session()
    user = User(username="admin", password_hash="x", is_admin=True)
    db.add(user)
    db.flush()
    run = ResearchRun(
        keyword="gempa bali",
        research_prompt="",
        language="id-ID",
        period_days=7,
        created_by=user.id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    candidates = run_discovery(run, db, MockWigoloClient())

    # The mock returns 3 distinct hits grouped by publisher -> at least 1, <=5.
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
