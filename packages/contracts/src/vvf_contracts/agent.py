"""Local render agent <-> VPS protocol contracts.

All endpoints under /api/v1/agents/* use these shapes. The agent never exposes
an inbound port; it polls outward with claim-job and posts events/complete/fail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from vvf_contracts.common import RenderJobStatus, utcnow
from vvf_contracts.render import RenderJobPayload


class AgentRegisterIn(BaseModel):
    """POST /api/v1/agents/register."""

    name: str = Field(..., examples=["render-pc-01"])
    version: str = "0.1.0"
    capabilities: list[str] = Field(default_factory=lambda: ["mpt", "edge_tts", "whisper"])
    available_disk_gb: float = 0.0
    mpt_base_url: str = "http://127.0.0.1:8080"
    # Read-only preview server reachable over Tailscale (e.g. http://100.x.y.z:8090).
    # Empty means no preview is available for this agent.
    preview_base_url: str = ""


class AgentRegisterOut(BaseModel):
    agent_id: str
    token: str
    expires_at: datetime | None = None


class AgentHeartbeatIn(BaseModel):
    """POST /api/v1/agents/heartbeat."""

    agent_id: str
    available_disk_gb: float = 0.0
    mpt_healthy: bool = True
    active_job_id: str | None = None
    sent_at: datetime = Field(default_factory=utcnow)


class ClaimJobIn(BaseModel):
    """POST /api/v1/agents/claim-job — claim one queued job for rendering."""

    agent_id: str
    idempotency_key: str | None = None


class ClaimJobOut(BaseModel):
    """Response: either a claimed job (with its immutable payload) or nothing."""

    claimed: bool = False
    job_id: str | None = None
    attempt: int = 0
    payload: RenderJobPayload | None = None


class AgentJobEventIn(BaseModel):
    """POST /api/v1/agents/jobs/{id}/events."""

    agent_id: str
    status: RenderJobStatus
    message: str = ""
    progress: int = Field(0, ge=0, le=100)
    log: str | None = None


class JobArtifact(BaseModel):
    """An output artifact produced by MPT that the agent uploads."""

    artifact_type: str  # mp4 | thumbnail | srt | script | provenance
    storage_url: str
    local_path: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None
    checksum: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentJobCompleteIn(BaseModel):
    """POST /api/v1/agents/jobs/{id}/complete."""

    agent_id: str
    artifacts: list[JobArtifact] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    final_script: str | None = None
    duration_seconds: float | None = None


class AgentJobFailIn(BaseModel):
    """POST /api/v1/agents/jobs/{id}/fail."""

    agent_id: str
    status: RenderJobStatus = RenderJobStatus.FAILED
    error_message: str
    retryable: bool = False
    last_log: str | None = None


__all__ = [
    "AgentHeartbeatIn",
    "AgentJobCompleteIn",
    "AgentJobEventIn",
    "AgentJobFailIn",
    "AgentRegisterIn",
    "AgentRegisterOut",
    "ClaimJobIn",
    "ClaimJobOut",
    "JobArtifact",
]
