"""Local render agent protocol endpoints (IMPLEMENTATION_PLAN.md section 10/11).

The local PC never exposes an inbound port; it polls outward. These endpoints
authenticate the agent with its per-agent token (issued at registration) and let
it claim + drive a render job.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select

from vvf_api.deps import DbSession
from vvf_api.routers.publish import _sync_job_status
from vvf_contracts.agent import (
    AgentHeartbeatIn,
    AgentJobCompleteIn,
    AgentJobEventIn,
    AgentJobFailIn,
    AgentRegisterIn,
    AgentRegisterOut,
    ClaimJobIn,
    ClaimJobOut,
)
from vvf_contracts.publish import (
    AgentPublishResultIn,
    ClaimPublishIn,
    ClaimPublishOut,
    PublishJobPayload,
)
from vvf_contracts.render import RenderJobPayload
from vvf_database.models import (
    Agent,
    PublishTarget,
    RenderJob,
    RenderJobEvent,
    VideoOutput,
)
from vvf_shared.security import TokenManager, hash_token

router = APIRouter(prefix="/agents", tags=["agents"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_manager() -> TokenManager:
    from vvf_shared.config import get_settings

    return TokenManager(get_settings().secret_key)


def get_agent(db: DbSession, authorization: str | None) -> Agent:
    """Resolve the calling agent from its bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing agent token")
    token = authorization.removeprefix("Bearer ").strip()
    fingerprint = hash_token(token)
    agent = db.execute(select(Agent).where(Agent.token_hash == fingerprint)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid agent token")
    return agent


def _fail404(what: str):
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def _fail401(msg: str):
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, msg)


@router.post("/register", response_model=AgentRegisterOut)
def register(body: AgentRegisterIn, db: DbSession) -> AgentRegisterOut:
    """Register a local render PC and issue a per-agent token (returned once)."""
    existing = db.execute(select(Agent).where(Agent.name == body.name)).scalar_one_or_none()
    tm = _token_manager()
    if existing is not None:
        token = tm.issue(existing.id)
        existing.token_hash = hash_token(token)
        existing.version = body.version
        existing.capabilities = body.capabilities
        existing.mpt_base_url = body.mpt_base_url
        existing.preview_base_url = body.preview_base_url
        existing.available_disk_gb = body.available_disk_gb
        db.commit()
        return AgentRegisterOut(agent_id=existing.id, token=token)

    agent = Agent(
        name=body.name,
        version=body.version,
        capabilities=body.capabilities,
        mpt_base_url=body.mpt_base_url,
        preview_base_url=body.preview_base_url,
        available_disk_gb=body.available_disk_gb,
        token_hash="",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    token = tm.issue(agent.id)
    agent.token_hash = hash_token(token)
    db.commit()
    return AgentRegisterOut(agent_id=agent.id, token=token)


@router.post("/heartbeat")
def heartbeat(body: AgentHeartbeatIn, db: DbSession) -> dict:
    agent = db.get(Agent, body.agent_id) or _fail404("agent")
    if not agent.token_hash:
        _fail401("agent not registered")
    agent.last_heartbeat_at = body.sent_at
    agent.available_disk_gb = body.available_disk_gb
    agent.mpt_healthy = body.mpt_healthy
    agent.active_job_id = body.active_job_id
    db.commit()
    return {"agent_id": agent.id, "ok": True}


@router.post("/claim-job", response_model=ClaimJobOut)
def claim_job(
    body: ClaimJobIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> ClaimJobOut:
    """Atomically claim the oldest queued job for the authenticated agent."""
    agent = get_agent(db, authorization)
    job = db.execute(
        select(RenderJob)
        .where(RenderJob.status == "queued")
        .order_by(RenderJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None:
        return ClaimJobOut(claimed=False)

    # Idempotency: a retry with the same key returns the already-claimed job.
    if (
        body.idempotency_key
        and job.idempotency_key == body.idempotency_key
        and job.claimed_by_agent_id == agent.id
    ):
        return ClaimJobOut(
            claimed=True,
            job_id=job.id,
            attempt=job.attempt,
            payload=_payload_for(job),
        )

    job.status = "claimed"
    job.claimed_by_agent_id = agent.id
    job.attempt += 1
    agent.active_job_id = job.id
    db.add(
        RenderJobEvent(
            job_id=job.id, agent_id=agent.id, status="claimed",
            message=f"claimed by {agent.name}", progress=0,
        )
    )
    db.commit()
    db.refresh(job)
    return ClaimJobOut(
        claimed=True, job_id=job.id, attempt=job.attempt, payload=_payload_for(job)
    )


def _payload_for(job: RenderJob) -> RenderJobPayload | None:
    if not job.payload_json:
        return None
    return RenderJobPayload(**job.payload_json)


@router.post("/jobs/{job_id}/events")
def post_job_event(
    job_id: str,
    body: AgentJobEventIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> dict:
    agent = get_agent(db, authorization)
    job = db.get(RenderJob, job_id) or _fail404("render job")
    if job.claimed_by_agent_id != agent.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "job not claimed by this agent")
    status_val = body.status.value if hasattr(body.status, "value") else str(body.status)
    job.status = status_val
    db.add(
        RenderJobEvent(
            job_id=job.id, agent_id=agent.id, status=status_val,
            message=body.message, progress=body.progress, log=body.log,
        )
    )
    db.commit()
    return {"ok": True, "status": job.status, "progress": body.progress}


@router.post("/jobs/{job_id}/complete")
def complete_job(
    job_id: str,
    body: AgentJobCompleteIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> dict:
    agent = get_agent(db, authorization)
    job = db.get(RenderJob, job_id) or _fail404("render job")
    if job.claimed_by_agent_id != agent.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "job not claimed by this agent")
    for art in body.artifacts:
        # Binary artifacts (mp4 / mp4_combined) are metadata-only: local_path on
        # the render PC + size/duration/checksum. The video file itself is never
        # stored on the VPS; it is previewed by proxying the PC over Tailscale.
        storage_url = art.storage_url or (art.local_path if art.local_path else "")
        db.add(
            VideoOutput(
                job_id=job.id,
                artifact_type=art.artifact_type,
                storage_url=storage_url,
                local_path=art.local_path,
                agent_id=agent.id,
                size_bytes=art.size_bytes,
                duration_seconds=art.duration_seconds,
                checksum=art.checksum,
                extra=art.extra,
            )
        )
    job.status = "completed"
    agent.active_job_id = None
    db.add(
        RenderJobEvent(
            job_id=job.id, agent_id=agent.id, status="completed",
            message="job completed", progress=100,
        )
    )
    db.commit()
    return {"ok": True, "job_id": job.id, "status": "completed"}


@router.post("/jobs/{job_id}/fail")
def fail_job(
    job_id: str,
    body: AgentJobFailIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> dict:
    agent = get_agent(db, authorization)
    job = db.get(RenderJob, job_id) or _fail404("render job")
    if job.claimed_by_agent_id != agent.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "job not claimed by this agent")
    new_status = "retry_waiting" if body.retryable else "failed"
    job.status = new_status
    job.error_message = body.error_message
    agent.active_job_id = None
    db.add(
        RenderJobEvent(
            job_id=job.id, agent_id=agent.id, status=new_status,
            message=body.error_message, progress=0, log=body.last_log,
        )
    )
    db.commit()
    return {"ok": True, "job_id": job.id, "status": new_status}


# ---------------------------------------------------------------------------
# Publishing (M6) — the agent publishes from the PC and reports the outcome.
# ---------------------------------------------------------------------------


@router.post("/claim-publish", response_model=ClaimPublishOut)
def claim_publish(
    body: ClaimPublishIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> ClaimPublishOut:
    """Claim all pending publish targets for the oldest job awaiting publishing.

    Targets are grouped per job so the agent uploads one file to several
    platforms in a single pass.
    """
    agent = get_agent(db, authorization)
    pending = db.execute(
        select(PublishTarget)
        .where(PublishTarget.status == "pending")
        .order_by(PublishTarget.created_at)
        .with_for_update(skip_locked=True)
    ).scalars().all()
    if not pending:
        return ClaimPublishOut(claimed=False)

    job_id = pending[0].job_id
    mine = [t for t in pending if t.job_id == job_id]

    # The artifact must be held by *this* agent — only it can read the file.
    artifact = db.execute(
        select(VideoOutput)
        .where(
            VideoOutput.job_id == job_id,
            VideoOutput.artifact_type.in_(("mp4", "mp4_combined")),
            VideoOutput.agent_id == agent.id,
        )
        .order_by(VideoOutput.created_at.desc())
    ).scalars().first()
    if artifact is None or not artifact.local_path:
        return ClaimPublishOut(claimed=False)

    meta = mine[0].request_json or {}
    for target in mine:
        target.status = "publishing"
        target.claimed_by_agent_id = agent.id
        target.attempt += 1
    db.add(
        RenderJobEvent(
            job_id=job_id,
            agent_id=agent.id,
            status="publishing",
            message="publishing to " + ", ".join(t.platform for t in mine),
            progress=100,
        )
    )
    db.commit()

    return ClaimPublishOut(
        claimed=True,
        payload=PublishJobPayload(
            job_id=job_id,
            target_ids=[t.id for t in mine],
            platforms=[t.platform for t in mine],
            mode=mine[0].mode,
            local_path=artifact.local_path,
            title=meta.get("title") or "Video",
            description=meta.get("description") or "",
            hashtags=meta.get("hashtags") or [],
            private=bool(meta.get("private")),
        ),
    )


@router.post("/jobs/{job_id}/publish-result")
def report_publish_result(
    job_id: str,
    body: AgentPublishResultIn,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> dict:
    """Record per-platform publish outcomes reported by the agent."""
    agent = get_agent(db, authorization)
    job = db.get(RenderJob, job_id) or _fail404("render job")

    targets = {
        t.platform: t
        for t in db.execute(
            select(PublishTarget).where(PublishTarget.job_id == job_id)
        ).scalars().all()
    }
    applied = 0
    for item in body.results:
        target = targets.get(item.platform.value)
        if target is None:
            continue
        if target.claimed_by_agent_id not in (None, agent.id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"{item.platform.value} target claimed by another agent"
            )
        target.status = item.status.value
        target.post_url = item.post_url
        target.platform_post_id = item.platform_post_id
        target.error_message = item.error_message
        if item.status.value == "published":
            target.published_at = _utcnow()
        db.add(
            RenderJobEvent(
                job_id=job_id,
                agent_id=agent.id,
                status="published" if item.status.value == "published" else "publishing",
                message=f"{item.platform.value}: {item.status.value}"
                + (f" -> {item.post_url}" if item.post_url else "")
                + (f" ({item.error_message})" if item.error_message else ""),
                progress=100,
            )
        )
        applied += 1

    _sync_job_status(db, job_id)
    db.commit()
    return {"ok": True, "job_id": job.id, "applied": applied, "status": job.status}


