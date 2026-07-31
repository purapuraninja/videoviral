"""HTTP client for the VVF VPS API (agent protocol).

Wraps the /api/v1/agents/* endpoints. The agent never exposes an inbound
port; it polls outward here (claim-job) and posts events/complete/fail.
"""

from __future__ import annotations

from typing import Any

import httpx

from vvf_contracts.agent import (
    AgentHeartbeatIn,
    AgentJobCompleteIn,
    AgentJobEventIn,
    AgentJobFailIn,
    AgentRegisterIn,
    AgentRegisterOut,
    ClaimJobIn,
    ClaimJobOut,
    JobArtifact,
)
from vvf_contracts.common import RenderJobStatus
from vvf_local_agent.config import AgentConfig


class VpsClient:
    """Thin typed wrapper over the VVF API agent endpoints."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._http = httpx.Client(timeout=60.0)
        self._agent_id: str | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.agent_token}"}

    def register(self) -> AgentRegisterOut:
        body = AgentRegisterIn(
            name=self._config.agent_name,
            version="0.1.0",
            capabilities=["mpt", "edge_tts", "whisper"],
            mpt_base_url=self._config.mpt_base_url,
            preview_base_url=self._config.preview_base_url(),
        )
        resp = self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/register",
            json=body.model_dump(),
        )
        resp.raise_for_status()
        out = AgentRegisterOut(**resp.json())
        self._agent_id = out.agent_id
        return out

    def heartbeat(self, *, available_disk_gb: float, mpt_healthy: bool, active_job_id: str | None) -> None:
        body = AgentHeartbeatIn(
            agent_id=self._agent_id or "",
            available_disk_gb=available_disk_gb,
            mpt_healthy=mpt_healthy,
            active_job_id=active_job_id,
        )
        self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/heartbeat",
            json=body.model_dump(mode="json"),
        )

    def claim_job(self, idempotency_key: str | None = None) -> ClaimJobOut | None:
        body = ClaimJobIn(agent_id=self._agent_id or "", idempotency_key=idempotency_key)
        resp = self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/claim-job",
            json=body.model_dump(),
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return ClaimJobOut(**resp.json())

    def post_event(self, job_id: str, status: RenderJobStatus, message: str = "", progress: int = 0) -> None:
        body = AgentJobEventIn(
            agent_id=self._agent_id or "",
            status=status,
            message=message,
            progress=progress,
        )
        self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/jobs/{job_id}/events",
            json=body.model_dump(mode="json"),
            headers=self._headers(),
        )

    def complete(self, job_id: str, artifacts: list[JobArtifact], provenance: dict[str, Any], final_script: str | None = None) -> None:
        body = AgentJobCompleteIn(
            agent_id=self._agent_id or "",
            artifacts=artifacts,
            provenance=provenance,
            final_script=final_script,
        )
        self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/jobs/{job_id}/complete",
            json=body.model_dump(mode="json"),
            headers=self._headers(),
        )

    def fail(self, job_id: str, error_message: str, retryable: bool = False, last_log: str | None = None) -> None:
        body = AgentJobFailIn(
            agent_id=self._agent_id or "",
            error_message=error_message,
            retryable=retryable,
            last_log=last_log,
        )
        self._http.post(
            f"{self._config.vps_api_url}/api/v1/agents/jobs/{job_id}/fail",
            json=body.model_dump(mode="json"),
            headers=self._headers(),
        )
