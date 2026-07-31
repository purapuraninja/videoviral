"""Research runs + candidate review endpoints.

Implements IMPLEMENTATION_PLAN.md §10:
    POST   /research-runs
    POST   /research-runs/{id}/start
    GET    /research-runs/{id}
    GET    /research-runs/{id}/candidates
    POST   /candidates/{id}/approve
    POST   /candidates/{id}/reject
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload  # noqa: F401  (used by future eager loads)

from vvf_api.deps import CurrentAdmin, DbSession
from vvf_api.queue import enqueue_discovery
from vvf_contracts.research import (
    CandidateOut,
    ResearchRunCreate,
    ResearchRunOut,
)
from vvf_database.models import ContentCandidate, ResearchRun

router = APIRouter(tags=["research"])


def _to_run_out(run: ResearchRun) -> ResearchRunOut:
    return ResearchRunOut(
        id=run.id,
        keyword=run.keyword,
        research_prompt=run.research_prompt or "",
        language=run.language,
        source_filters=run.source_filters or {},
        period_days=run.period_days,
        platforms=run.platforms or [],
        render_profile_id=run.render_profile_id,
        created_by=run.created_by,
        status=run.status,
        candidate_count=len(run.candidates),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/research-runs", response_model=list[ResearchRunOut])
def list_research_runs(db: DbSession, admin: CurrentAdmin) -> list[ResearchRunOut]:
    runs = db.execute(select(ResearchRun).order_by(ResearchRun.created_at.desc())).scalars().all()
    return [_to_run_out(r) for r in runs]


@router.post("/research-runs", response_model=ResearchRunOut, status_code=status.HTTP_201_CREATED)
def create_research_run(body: ResearchRunCreate, db: DbSession, admin: CurrentAdmin) -> ResearchRunOut:
    run = ResearchRun(
        keyword=body.keyword,
        research_prompt=body.research_prompt,
        language=body.language.value,
        source_filters=body.source_filters,
        period_days=body.period_days,
        platforms=body.platforms,
        render_profile_id=body.render_profile_id,
        created_by=admin,
        status="draft",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _to_run_out(run)


@router.post("/research-runs/{run_id}/start", response_model=ResearchRunOut)
def start_research_run(run_id: str, db: DbSession, admin: CurrentAdmin) -> ResearchRunOut:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "research run not found")
    if run.status in ("running", "completed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"run already {run.status}")
    run.status = "running"
    db.commit()
    db.refresh(run)
    # Hand the run to the discovery worker via Redis.
    enqueue_discovery(run.id)
    return _to_run_out(run)


@router.get("/research-runs/{run_id}", response_model=ResearchRunOut)
def get_research_run(run_id: str, db: DbSession, admin: CurrentAdmin) -> ResearchRunOut:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "research run not found")
    return _to_run_out(run)


@router.get("/research-runs/{run_id}/candidates", response_model=list[CandidateOut])
def list_candidates(run_id: str, db: DbSession, admin: CurrentAdmin) -> list[CandidateOut]:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "research run not found")
    stmt = (
        select(ContentCandidate)
        .where(ContentCandidate.research_run_id == run_id)
        .order_by(ContentCandidate.rank.asc(), ContentCandidate.final_score.desc())
    )
    candidates = db.execute(stmt).scalars().all()
    out: list[CandidateOut] = []
    for c in candidates:
        out.append(
            CandidateOut(
                id=c.id,
                research_run_id=c.research_run_id,
                title=c.title,
                summary=c.summary,
                facts=c.facts_json or [],
                source_ids=[],
                source_links=c.source_links or [],
                virality_score=c.virality_score,
                freshness_score=c.freshness_score,
                source_score=c.source_score,
                relevance_score=c.relevance_score,
                risk_score=c.risk_score,
                final_score=c.final_score,
                rank=c.rank,
                risk_flags=c.risk_flags or [],
                language=c.language,
                status=c.status,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return out


@router.post("/candidates/{candidate_id}/approve", status_code=status.HTTP_200_OK)
def approve_candidate(candidate_id: str, db: DbSession, admin: CurrentAdmin) -> dict:
    cand = db.get(ContentCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "candidate not found")
    if cand.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"candidate already {cand.status}")
    cand.status = "approved"
    db.commit()
    # Render job creation happens in the render router/approval flow (Milestone 2).
    return {"candidate_id": candidate_id, "status": "approved", "approved_by": admin}


@router.post("/candidates/{candidate_id}/reject", status_code=status.HTTP_200_OK)
def reject_candidate(candidate_id: str, db: DbSession, admin: CurrentAdmin) -> dict:
    cand = db.get(ContentCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "candidate not found")
    cand.status = "rejected"
    db.commit()
    return {"candidate_id": candidate_id, "status": "rejected"}
