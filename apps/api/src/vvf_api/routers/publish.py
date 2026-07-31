"""Publishing endpoints (M6).

Publishing happens on the render PC (that is where the video lives). These
endpoints only orchestrate and record:

- ``POST /render-jobs/{id}/publish``      admin queues publish targets
- ``GET  /render-jobs/{id}/publish-targets``  per-platform status + post URLs
- ``POST /publish-targets/{id}/manual``   admin records a hand-uploaded post URL
- ``POST /publish-targets/{id}/retry``    reset a failed target back to pending

No video bytes and no OAuth credentials ever touch the VPS.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from vvf_api.deps import CurrentAdmin, DbSession
from vvf_contracts.publish import (
    ManualPublishIn,
    PublishRequest,
    PublishTargetOut,
)
from vvf_database.models import PublishTarget, RenderJob, RenderJobEvent, VideoOutput

router = APIRouter(tags=["publish"])

# A job must have a previewable artifact before it can be published.
_PREVIEWABLE = ("mp4", "mp4_combined")
# Targets that can be re-queued or replaced by a new publish request.
_RESETTABLE = ("failed", "manual_required", "skipped")


def _target_out(t: PublishTarget) -> PublishTargetOut:
    return PublishTargetOut(
        id=t.id,
        job_id=t.job_id,
        platform=t.platform,
        mode=t.mode,
        status=t.status,
        post_url=t.post_url,
        platform_post_id=t.platform_post_id,
        error_message=t.error_message,
        attempt=t.attempt,
        published_at=t.published_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post(
    "/render-jobs/{job_id}/publish",
    response_model=list[PublishTargetOut],
    status_code=status.HTTP_201_CREATED,
)
def request_publish(
    job_id: str, body: PublishRequest, db: DbSession, admin: CurrentAdmin
) -> list[PublishTargetOut]:
    """Queue publish targets for a completed render job.

    Idempotent per platform: an existing target that already published is left
    untouched; a failed/manual one is reset to ``pending`` for another attempt.
    """
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    if job.status not in ("completed", "publishing", "published", "publish_failed"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"job must be completed before publishing (is {job.status})"
        )

    artifact = db.execute(
        select(VideoOutput)
        .where(VideoOutput.job_id == job_id, VideoOutput.artifact_type.in_(_PREVIEWABLE))
        .order_by(VideoOutput.created_at.desc())
    ).scalars().first()
    if artifact is None or not artifact.local_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "job has no video artifact to publish")

    request_meta = {
        "title": body.title or (job.payload_json or {}).get("candidate", {}).get("title") or "Video",
        "description": body.description
        or (job.payload_json or {}).get("candidate", {}).get("summary")
        or "",
        "hashtags": body.hashtags,
        "private": body.private,
    }

    existing = {
        t.platform: t
        for t in db.execute(
            select(PublishTarget).where(PublishTarget.job_id == job_id)
        ).scalars().all()
    }

    out: list[PublishTarget] = []
    for platform in body.platforms:
        key = platform.value
        target = existing.get(key)
        if target is None:
            target = PublishTarget(
                job_id=job_id,
                platform=key,
                mode=body.mode.value,
                status="pending",
                request_json=request_meta,
            )
            db.add(target)
        elif target.status in _RESETTABLE:
            target.status = "pending"
            target.mode = body.mode.value
            target.request_json = request_meta
            target.error_message = None
            target.claimed_by_agent_id = None
        out.append(target)

    # Only advance the job if something is actually queued.
    if any(t.status == "pending" for t in out):
        job.status = "publishing"
        db.add(
            RenderJobEvent(
                job_id=job.id,
                status="publishing",
                message="publish requested for " + ", ".join(p.value for p in body.platforms),
                progress=100,
            )
        )

    db.commit()
    for t in out:
        db.refresh(t)
    return [_target_out(t) for t in out]


@router.get("/render-jobs/{job_id}/publish-targets", response_model=list[PublishTargetOut])
def list_publish_targets(
    job_id: str, db: DbSession, admin: CurrentAdmin
) -> list[PublishTargetOut]:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "render job not found")
    rows = db.execute(
        select(PublishTarget)
        .where(PublishTarget.job_id == job_id)
        .order_by(PublishTarget.created_at)
    ).scalars().all()
    return [_target_out(t) for t in rows]


@router.post("/publish-targets/{target_id}/manual", response_model=PublishTargetOut)
def record_manual_publish(
    target_id: str, body: ManualPublishIn, db: DbSession, admin: CurrentAdmin
) -> PublishTargetOut:
    """Record a post the admin uploaded by hand (the manual fallback)."""
    target = db.get(PublishTarget, target_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "publish target not found")

    target.status = "published"
    target.mode = "manual"
    target.post_url = body.post_url
    target.platform_post_id = body.platform_post_id
    target.error_message = None
    target.published_at = _utcnow()
    db.add(
        RenderJobEvent(
            job_id=target.job_id,
            status="published",
            message=f"{target.platform} published manually: {body.post_url}",
            progress=100,
        )
    )
    _sync_job_status(db, target.job_id)
    db.commit()
    db.refresh(target)
    return _target_out(target)


@router.post("/publish-targets/{target_id}/retry", response_model=PublishTargetOut)
def retry_publish_target(
    target_id: str, db: DbSession, admin: CurrentAdmin
) -> PublishTargetOut:
    """Re-queue a failed/manual target for another automatic attempt."""
    target = db.get(PublishTarget, target_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "publish target not found")
    if target.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "target already published")

    target.status = "pending"
    target.error_message = None
    target.claimed_by_agent_id = None
    job = db.get(RenderJob, target.job_id)
    if job is not None:
        job.status = "publishing"
    db.commit()
    db.refresh(target)
    return _target_out(target)


def _sync_job_status(db, job_id: str) -> None:
    """Reflect target states onto the render job.

    ``published``      every target reached a terminal-good state
    ``publishing``     work is still outstanding — either the agent is running or
                       a target is ``manual_required`` and awaits the admin
    ``publish_failed`` nothing succeeded, nothing is outstanding, something failed

    ``manual_required`` deliberately counts as outstanding rather than failed: it
    is a request for admin action, and the job resolves once the admin records
    the post URL (or retries automatically).
    """
    job = db.get(RenderJob, job_id)
    if job is None:
        return
    states = [
        t.status
        for t in db.execute(
            select(PublishTarget).where(PublishTarget.job_id == job_id)
        ).scalars().all()
    ]
    if not states:
        return
    outstanding = {"pending", "publishing", "manual_required"}
    if any(s in outstanding for s in states):
        job.status = "publishing"
    elif all(s in ("published", "skipped") for s in states):
        job.status = "published"
    elif any(s == "published" for s in states):
        # Partial success: some platforms live, others failed terminally.
        job.status = "published"
    else:
        job.status = "publish_failed"
