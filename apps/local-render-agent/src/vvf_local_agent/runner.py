"""Render runner: claim a job, drive MPT, report events, upload artifacts.

Core of the local PC agent (IMPLEMENTATION_PLAN.md section 11). MPT generates the
script itself during the task (we pass an empty video_script and read the final
script back from the task result), so we don't depend on the /scripts endpoint.
"""

from __future__ import annotations

import time
from typing import Any

from vvf_contracts.agent import JobArtifact
from vvf_contracts.common import RenderJobStatus
from vvf_contracts.mpt import MPTVideoParams
from vvf_mpt import MPTClient, MPTState, MockMPTClient, map_state_to_vvf_status
from vvf_shared.logging import get_logger


class RenderRunner:
    """Runs a single claimed job through MoneyPrinterTurbo."""

    def __init__(self, mpt: MPTClient | MockMPTClient, mpt_base_url: str = "http://127.0.0.1:8080") -> None:
        self._mpt = mpt
        self._mpt_base = mpt_base_url.rstrip("/")
        self._log = get_logger()
        # Root dir the preview server serves; must contain the rendered MP4s.
        import os

        self._preview_root = os.path.abspath(
            os.getenv("VVF_PREVIEW_ROOT", os.path.join("MoneyPrinterTurbo", "storage", "tasks"))
        )

    def run(self, vps, job_id: str, payload: Any, idempotency_key: str) -> None:
        """Execute one render job, posting events + final artifacts back to VPS."""
        candidate = payload.candidate
        video = payload.video

        try:
            vps.post_event(job_id, RenderJobStatus.SCRIPTING, "preparing MPT task", 5)
            # Let MPT generate the script (pass empty video_script).
            params = MPTVideoParams.from_payload(payload, script="")
            vps.post_event(job_id, RenderJobStatus.ASSETS, "creating MPT task", 10)
            mpt_task_id = self._mpt.create_video(params)
            self._log.info(f"job {job_id} -> MPT task {mpt_task_id}")
            vps.post_event(job_id, RenderJobStatus.TTS, f"MPT task {mpt_task_id}", 20)

            status = self._poll_with_events(vps, job_id, mpt_task_id)

            if status.state == MPTState.ERROR:
                vps.fail(
                    job_id,
                    error_message=status.error or "MPT render failed",
                    retryable=True,
                    last_log=status.raw.get("error") if isinstance(status.raw, dict) else None,
                )
                return

            # MPT returns the generated script in the final task payload.
            script = status.script or ""

            # The rendered MP4 stays on this PC. We report metadata only:
            # local paths so the VPS can build a Tailscale preview URL, plus
            # script + provenance (small, sent inline via complete()).
            vps.post_event(job_id, RenderJobStatus.UPLOADING, "recording output metadata", 95)
            artifacts = self._artifacts(script, payload, mpt_task_id, status)
            provenance = artifacts[-1].extra if artifacts else {}
            vps.complete(job_id, artifacts=artifacts, provenance=provenance, final_script=script)
        except Exception as exc:  # pragma: no cover - error path
            self._log.exception(f"job {job_id} failed: {exc}")
            vps.fail(job_id, error_message=str(exc), retryable=False, last_log=None)

    def _poll_with_events(self, vps, job_id: str, mpt_task_id: str):
        last_progress = -1
        deadline = time.monotonic() + 1800.0
        while time.monotonic() < deadline:
            status = self._mpt.get_task(mpt_task_id)
            if status.progress != last_progress:
                vvf_status = map_state_to_vvf_status(status)
                vps.post_event(
                    job_id, vvf_status, f"MPT progress {status.progress}%",
                    progress=min(90, 25 + status.progress // 2),
                )
                last_progress = status.progress
            if status.state in (MPTState.SUCCESS, MPTState.ERROR):
                return status
            time.sleep(5.0)
        raise TimeoutError("MPT task timed out")

    def _abs(self, url: str) -> str:
        """Make MPT-relative task paths absolute (e.g. /tasks/x/final-1.mp4)."""
        if not url:
            return url
        if url.startswith(("http://", "https://", "data:")):
            return url
        if url.startswith("/"):
            return f"{self._mpt_base}{url}"
        return f"{self._mpt_base}/{url}"

    def _artifacts(self, script, payload, mpt_task_id, status):
        """Build the metadata-only artifact list sent via complete().

        Video binaries are referenced by local path on this PC (never uploaded);
        script + provenance are small and sent inline as data URIs.
        """
        import json
        import os

        prov = self._build_provenance(payload, mpt_task_id, status, script)
        artifacts: list[JobArtifact] = []

        # Binary outputs: metadata only — a persistent path the preview server can
        # serve, plus size when we can stat it via MPT's storage root.
        for atype, urls in (("mp4", status.videos), ("mp4_combined", status.combined_videos)):
            for url in urls or []:
                full = self._abs(url)
                serve_path = self._serve_path(full)
                abs_local = self._abs_local_path(serve_path)
                size = None
                try:
                    if os.path.isfile(abs_local):
                        size = os.path.getsize(abs_local)
                except OSError:
                    pass
                artifacts.append(
                    JobArtifact(
                        artifact_type=atype,
                        storage_url="",
                        local_path=serve_path,  # web path under the preview server root
                        size_bytes=size,
                        extra={"abs_local_path": abs_local},
                    )
                )

        # Small text artifacts (script + provenance) carried inline.
        if script:
            artifacts.append(JobArtifact(artifact_type="script", storage_url=_data_uri(script, "text/plain")))
        artifacts.append(
            JobArtifact(
                artifact_type="provenance",
                storage_url=_data_uri(json.dumps(prov), "application/json"),
                extra=prov,
            )
        )
        return artifacts

    def _build_provenance(self, payload, mpt_task_id, status, script) -> dict[str, Any]:
        return {
            "job_id": payload.job_id,
            "idempotency_key": payload.idempotency_key,
            "mpt_task_id": mpt_task_id,
            "candidate_title": payload.candidate.title,
            "sources": payload.candidate.sources,
            "script": script,
            "video_outputs": [self._abs(u) for u in status.videos],
            "model_settings": {
                "video_aspect": payload.video.aspect_ratio.value,
                "language": payload.video.language.value,
                "voice": payload.creative.voice,
            },
        }

    def _serve_path(self, full_url: str) -> str:
        """Return the path of a rendered file relative to the MPT tasks dir.

        MPT task URLs look like ``{mpt_base}/tasks/{task_id}/final-1.mp4``; the
        preview server serves under the tasks root, so the web path is
        ``{task_id}/final-1.mp4`` (no ``/tasks/`` prefix).
        """
        import os
        from urllib.parse import urlparse

        path = urlparse(full_url).path if full_url.startswith(("http://", "https://")) else full_url
        if path.startswith("/tasks/"):
            path = path[len("/tasks/"):]
        return path.lstrip("/")

    def _abs_local_path(self, serve_path: str) -> str:
        """Absolute filesystem path for a serve path under the preview root."""
        import os

        return os.path.join(self._preview_root, serve_path.replace("/", os.sep))


def _data_uri(text: str, mime: str) -> str:
    import base64

    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"data:{mime};base64,{b64}"

