"""Local render agent main loop.

- registers with the VPS (obtains a per-agent token)
- sends heartbeats every N seconds
- long-polls claim-job; on a claim, runs the job via MPT and posts events
"""

from __future__ import annotations

import sys
import threading
import time

from vvf_local_agent.api_client import VpsClient
from vvf_local_agent.config import AgentConfig
from vvf_local_agent.preview import start_preview_server
from vvf_local_agent.runner import RenderRunner
from vvf_mpt import MPTClient, MockMPTClient
from vvf_shared.logging import configure_logging, get_logger


def _make_mpt(config: AgentConfig):
    return MockMPTClient() if config.use_mock_mpt else MPTClient(base_url=config.mpt_base_url)


def _heartbeat_loop(config: AgentConfig, vps: VpsClient, stop: threading.Event) -> None:
    log = get_logger()
    while not stop.is_set():
        try:
            vps.heartbeat(
                available_disk_gb=50.0,
                mpt_healthy=True,
                active_job_id=None,
            )
        except Exception as exc:  # pragma: no cover
            log.warning(f"heartbeat failed: {exc}")
        stop.wait(config.heartbeat_interval)


def main() -> int:
    import os

    config = AgentConfig()
    configure_logging(os.getenv("VVF_LOG_LEVEL", "INFO"))
    log = get_logger()

    vps = VpsClient(config)
    reg = vps.register()
    # Persist the issued token back into config so subsequent calls use it.
    config.agent_token = reg.token
    log.info(f"registered as agent {reg.agent_id}")

    mpt = _make_mpt(config)
    runner = RenderRunner(mpt, config.mpt_base_url)

    # Read-only preview server for dashboard playback over Tailscale. Bind to the
    # Tailscale interface (VVF_PREVIEW_HOST); loopback-only means "no preview".
    preview = None
    if config.preview_base_url():
        try:
            preview = start_preview_server(config.preview_host, config.preview_port, config.preview_root)
        except OSError as exc:  # pragma: no cover
            log.warning(f"preview server not started: {exc}")

    stop = threading.Event()
    hb = threading.Thread(target=_heartbeat_loop, args=(config, vps, stop), daemon=True)
    hb.start()

    log.info("local render agent ready, polling for jobs")
    try:
        while not stop.is_set():
            claimed = vps.claim_job()
            if claimed is None or not claimed.claimed or claimed.payload is None:
                time.sleep(config.poll_interval)
                continue
            log.info(f"claimed job {claimed.job_id} attempt {claimed.attempt}")
            runner.run(vps, claimed.job_id, claimed.payload, claimed.payload.idempotency_key)
    except KeyboardInterrupt:  # pragma: no cover
        log.info("shutdown requested")
        stop.set()
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
