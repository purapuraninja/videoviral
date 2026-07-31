"""Local agent configuration (env-driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    vps_api_url: str = os.getenv("VVF_API_URL", "http://localhost:8000")
    agent_name: str = os.getenv("VVF_AGENT_NAME", "render-pc-01")
    agent_token: str = os.getenv("VVF_AGENT_TOKEN", "")
    mpt_base_url: str = os.getenv("MPT_BASE_URL", "http://127.0.0.1:8080")
    heartbeat_interval: float = float(os.getenv("VVF_HEARTBEAT_INTERVAL", "30"))
    poll_interval: float = float(os.getenv("VVF_POLL_INTERVAL", "5"))
    use_mock_mpt: bool = os.getenv("VVF_MPT_USE_MOCK", "0") == "1"
    # Read-only preview server that serves rendered files to the VPS over Tailscale.
    # VVF_PREVIEW_HOST should be the Tailscale interface IP (or the Tailscale IP); never 0.0.0.0/public.
    preview_host: str = os.getenv("VVF_PREVIEW_HOST", "127.0.0.1")
    preview_port: int = int(os.getenv("VVF_PREVIEW_PORT", "8090"))
    # Root directory holding rendered videos (MPT tasks dir).
    preview_root: str = os.getenv(
        "VVF_PREVIEW_ROOT",
        os.path.join("MoneyPrinterTurbo", "storage", "tasks"),
    )

    def preview_base_url(self) -> str:
        """Base URL other hosts use to reach this PC's preview server.

        Must be the Tailscale address (or explicit VVF_PREVIEW_BASE_URL).
        Returns empty string when preview is disabled/loopback-only so the VPS
        knows not to offer proxying.
        """
        explicit = os.getenv("VVF_PREVIEW_BASE_URL", "").strip()
        if explicit:
            return explicit.rstrip("/")
        if self.preview_host in ("127.0.0.1", "localhost", ""):
            return ""
        return f"http://{self.preview_host}:{self.preview_port}"
