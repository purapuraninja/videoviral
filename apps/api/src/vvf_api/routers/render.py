"""Render profiles + render jobs + job events endpoints.

Implements IMPLEMENTATION_PLAN.md section 10:
    GET    /render-profiles
    POST   /render-profiles
    GET    /render-jobs/{id}
    POST   /render-jobs/{id}/cancel
    GET    /render-jobs/{id}/events
    POST   /candidates/{id}/render-jobs?profile_name=...  (create immutable job)
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from starlette.background import BackgroundTask

from vvf_api.deps import CurrentAdmin, DbSession
from vvf_contracts.render import (
    RenderJobEventOut,
    RenderJobOut,
    RenderProfileCreate,
    RenderProfileOut,
    VideoOutputOut,
)
from vvf_database.models import (
    Agent,
    ContentCandidate,
    RenderJob,
    RenderJobEvent,
    RenderProfile,
    VideoOutput,
)
from vvf_shared.security import generate_idempotency_key

router = APIRouter(tags=["render"])

# Video artifact types that can be previewed by proxying the PC over Tailscale.
_PREVIEWABLE = {"mp4", "mp4_combined"}


def _preview_url_for(job_id: str, artifact_type: str, agent_id: str | None, local_path: str | None) -> str | None:
    """Expose a dashboard-facing preview URL for binary artifacts held on a PC."""
    if artifact_type not in _PREVIEWABLE or not agent_id or not local_path:
        return None
    return f"/render-jobs/{job_id}/preview?type={artifact_type}"


def _profile_out(p: RenderProfile) -> RenderProfileOut:
    return RenderProfileOut(
        id=p.id,
        name=p.name,
        aspect_ratio=p.aspect_ratio,
        resolution=p.resolution,
        duration_seconds=p.duration_seconds,
        language=p.language,
        platforms=p.platforms or [],
        voice_config=p.voice_config or {},
        subtitle_config=p.subtitle_config or {},
        music_config=p.music_config or {},
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/render-profiles", response_model=list[RenderProfileOut])
def list_profiles(db: DbSession, admin: CurrentAdmin) -> list[RenderProfileOut]:
    rows = db.execute(select(RenderProfile).order_by(RenderProfile.created_at)).scalars().all()
    return [_profile_out(p) for p in rows]


@router.post("/render-profiles", response_model=RenderProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(body: RenderProfileCreate, db: DbSession, admin: CurrentAdmin) -> RenderProfileOut:
    p = RenderProfile(
        name=body.name,
        aspect_ratio=body.aspect_ratio.value,
        resolution=body.resolution,
        duration_seconds=body.duration_seconds,
        language=body.language.value,
        platforms=body.platforms,
        voice_config=body.voice_config,
        subtitle_config=body.subtitle_config,
        music_config=body.music_config,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _profile_out(p)


def _job_out(job: RenderJob) -> RenderJobOut:
    return RenderJobOut(
        id=job.id,
        candidate_id=job.candidate_id,
        render_profile_id=job.render_profile_id,
        status=job.status,
        payload_json=job.payload_json,
        claimed_by_agent_id=job.claimed_by_agent_id,
        attempt=job.attempt,
        error_message=job.error_message,
        idempotency_key=job.idempotency_key,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def build_render_payload(candidate: ContentCandidate, profile: RenderProfile) -> dict:
    """Compose the immutable render job payload (IMPLEMENTATION_PLAN.md section 10)."""
    payload = {
        "job_id": "",
        "idempotency_key": "",
        "candidate": {
            "title": candidate.title,
            "facts": candidate.facts_json or [],
            "summary": candidate.summary,
            "sources": candidate.source_links or [],
        },
        "video": {
            "aspect_ratio": profile.aspect_ratio,
            "resolution": profile.resolution,
            "duration_seconds": profile.duration_seconds,
            "language": profile.language,
            "platforms": profile.platforms or [],
        },
        "creative": {
            "hook": None,
            "tone": "informative-fast",
            "voice": (profile.voice_config or {}).get("voice", "id-ID-ArdiNeural"),
            "subtitle_style": (profile.subtitle_config or {}).get("style", "bold-center"),
            "music_profile": (profile.music_config or {}).get("profile", "news-modern"),
            "video_source": "pexels",
        },
        "sources": candidate.source_links or [],
    }
    return payload


@router.post("/candidates/{candidate_id}/render-jobs", response_model=RenderJobOut, status_code=status.HTTP_201_CREATED)
def create_render_job(
    candidate_id: str,
    profile_name: str,
    db: DbSession,
    admin: CurrentAdmin,
) -> RenderJobOut:
    """Create an immutable render job from an approved candidate."""
    cand = db.get(ContentCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "candidate not found")
    if cand.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "candidate must be approved first")
    profile = db.execute(
        select(RenderProfile).where(RenderProfile.name == profile_name)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"render profile '{profile_name}' not found")

    idem = generate_idempotency_key()
    payload = build_render_payload(cand, profile)
    job = RenderJob(
        candidate_id=cand.id,
        render_profile_id=profile.id,
        status="queued",
        payload_json={**payload, "idempotency_key": idem},
        idempotency_key=idem,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    # Backfill the stable job id into the stored payload.
    job.payload_json = {**payload, "job_id": job.id, "idempotency_key": idem}
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.get("/render-jobs", response_model=list[RenderJobOut])
def list_render_jobs(
    db: DbSession, admin: CurrentAdmin, status_filter: str | None = None
) -> list[RenderJobOut]:
    stmt = select(RenderJob).order_by(RenderJob.created_at.desc())
    if status_filter:
        stmt = stmt.where(RenderJob.status == status_filter)
    rows = db.execute(stmt).scalars().all()
    return [_job_out(j) for j in rows]


@router.get("/render-jobs/{job_id}", response_model=RenderJobOut)
def get_render_job(job_id: str, db: DbSession, admin: CurrentAdmin) -> RenderJobOut:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    return _job_out(job)


@router.post("/render-jobs/{job_id}/cancel", response_model=RenderJobOut)
def cancel_render_job(job_id: str, db: DbSession, admin: CurrentAdmin) -> RenderJobOut:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    if job.status in ("completed", "cancelled", "failed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"job already {job.status}")
    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.get("/render-jobs/{job_id}/events", response_model=list[RenderJobEventOut])
def list_job_events(job_id: str, db: DbSession, admin: CurrentAdmin) -> list[RenderJobEventOut]:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    events = db.execute(
        select(RenderJobEvent)
        .where(RenderJobEvent.job_id == job_id)
        .order_by(RenderJobEvent.created_at)
    ).scalars().all()
    return [
        RenderJobEventOut(
            id=e.id,
            job_id=e.job_id,
            agent_id=e.agent_id,
            status=e.status,
            message=e.message,
            progress=e.progress,
            log=e.log,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/render-jobs/{job_id}/outputs", response_model=list[VideoOutputOut])
def list_job_outputs(job_id: str, db: DbSession, admin: CurrentAdmin) -> list[VideoOutputOut]:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    rows = db.execute(
        select(VideoOutput)
        .where(VideoOutput.job_id == job_id)
        .order_by(VideoOutput.created_at)
    ).scalars().all()
    return [
        VideoOutputOut(
            id=o.id,
            job_id=o.job_id,
            artifact_type=o.artifact_type,
            storage_url=o.storage_url,
            local_path=o.local_path,
            agent_id=o.agent_id,
            size_bytes=o.size_bytes,
            duration_seconds=o.duration_seconds,
            checksum=o.checksum,
            preview_url=_preview_url_for(o.job_id, o.artifact_type, o.agent_id, o.local_path),
            created_at=o.created_at,
        )
        for o in rows
    ]


@router.get("/render-jobs/{job_id}/preview")
async def preview_job_output(
    job_id: str,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    type: str = "mp4",
) -> StreamingResponse:
    """Stream a rendered video from the render PC over Tailscale (no VPS storage).

    Resolves which agent holds the artifact, then reverse-proxies the PC's
    read-only preview server (bound to the Tailscale interface). Range requests
    are forwarded so the dashboard <video> tag can seek. Bytes pass straight
    through — nothing is written to VPS disk.
    """
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")

    row = db.execute(
        select(VideoOutput)
        .where(VideoOutput.job_id == job_id, VideoOutput.artifact_type == type)
        .order_by(VideoOutput.created_at.desc())
    ).scalars().first()
    if row is None or not row.local_path or not row.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no previewable artifact for this job")

    agent = db.get(Agent, row.agent_id)
    if agent is None or not agent.preview_base_url:
        raise HTTPException(status.HTTP_409_CONFLICT, "holding agent has no preview server registered")

    upstream = f"{agent.preview_base_url.rstrip('/')}/{row.local_path.lstrip('/')}"
    fwd_headers = {}
    if rng := request.headers.get("range"):
        fwd_headers["Range"] = rng

    # Open the upstream stream now so we can mirror its status/headers, and hand
    # cleanup to a BackgroundTask so the connection outlives this handler.
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None), follow_redirects=True)
    try:
        req = client.build_request("GET", upstream, headers=fwd_headers)
        upstream_resp = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"preview upstream unreachable: {exc}")

    if upstream_resp.status_code >= 400:
        code = upstream_resp.status_code
        await upstream_resp.aclose()
        await client.aclose()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND if code == 404 else status.HTTP_502_BAD_GATEWAY,
            f"preview upstream returned {code}",
        )

    async def _cleanup() -> None:
        await upstream_resp.aclose()
        await client.aclose()

    resp_headers = {
        h: v
        for h in ("Content-Length", "Content-Range", "Accept-Ranges")
        if (v := upstream_resp.headers.get(h))
    }
    resp_headers.setdefault("Accept-Ranges", "bytes")
    return StreamingResponse(
        upstream_resp.aiter_bytes(chunk_size=65536),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=upstream_resp.headers.get("Content-Type", "video/mp4"),
        background=BackgroundTask(_cleanup),
    )


