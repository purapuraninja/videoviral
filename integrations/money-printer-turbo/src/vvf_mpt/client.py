"""MoneyPrinterTurbo API adapter.

MoneyPrinterTurbo (MPT) runs locally on the render PC as a FastAPI service on
port 8080 (``python main.py``). This adapter invokes its documented REST API
first and only falls back to the CLI when an API capability is unavailable.

Reference (MPT main branch, app/controllers/v1/video.py):
    POST /api/v1/videos        -> create task (body: TaskVideoRequest)
    GET  /api/v1/tasks/{id}    -> { state, progress, script, videos, combined_videos }
    DELETE /api/v1/tasks/{id}  -> delete/cancel task
    POST /api/v1/videos/script -> generate script for a subject
    POST /api/v1/videos/terms  -> generate search terms for a subject
    GET  /api/v1/voices        -> list supported voices

Task state codes (app/services/state.py):
    -1 = error / failure, 0 = no result yet, 1 = success, 9 = in progress/queued
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from vvf_contracts.common import RenderJobStatus
from vvf_contracts.mpt import MPTVideoParams
from vvf_shared.config import get_settings


class MPTState:
    """MPT numeric task states."""

    ERROR = -1
    NO_RESULT = 0
    SUCCESS = 1
    IN_PROGRESS = 9


@dataclass
class MPTTaskStatus:
    """Mapped status of an MPT task, normalized into VVF terms."""

    task_id: str
    state: int
    progress: int = 0
    script: str = ""
    videos: list[str] = field(default_factory=list)
    combined_videos: list[str] = field(default_factory=list)
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def map_state_to_vvf_status(status: MPTTaskStatus) -> RenderJobStatus:
    """Map MPT state into the VVF render-job status enum."""
    if status.state == MPTState.SUCCESS:
        return RenderJobStatus.COMPLETED
    if status.state == MPTState.ERROR:
        return RenderJobStatus.FAILED
    if status.progress >= 90:
        return RenderJobStatus.UPLOADING
    if status.progress >= 60:
        return RenderJobStatus.RENDERING
    if status.progress >= 30:
        return RenderJobStatus.TTS
    if status.progress > 0:
        return RenderJobStatus.ASSETS
    return RenderJobStatus.SCRIPTING


class MPTClient:
    """HTTP adapter for the MoneyPrinterTurbo REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.mpt_base_url).rstrip("/")
        self._token = token or settings.mpt_api_token
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def create_video(self, params: MPTVideoParams) -> str:
        """POST /api/v1/videos -> returns the MPT task id.

        MPT accepts the VideoParams fields directly (TaskVideoRequest is the
        params schema, not a wrapper), so we send ``params`` without a
        ``video_params`` envelope.
        """
        resp = self._client.post(
            self._url("/api/v1/videos"),
            json=params.model_dump(exclude_none=True),
            headers=self._headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {}) if isinstance(body, dict) else {}
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"MPT did not return a task id: {body}")
        return str(task_id)

    def get_task(self, task_id: str) -> MPTTaskStatus:
        """GET /api/v1/tasks/{id} -> mapped status."""
        resp = self._client.get(
            self._url(f"/api/v1/tasks/{task_id}"), headers=self._headers()
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {}) if isinstance(body, dict) else {}
        state = int(data.get("state", MPTState.NO_RESULT))
        return MPTTaskStatus(
            task_id=task_id,
            state=state,
            progress=int(data.get("progress", 0)),
            script=data.get("script", "") or "",
            videos=list(data.get("videos", []) or []),
            combined_videos=list(data.get("combined_videos", []) or []),
            error=data.get("error"),
            raw=data,
        )

    def delete_task(self, task_id: str) -> None:
        """DELETE /api/v1/tasks/{id} -> cancel/remove a task."""
        resp = self._client.delete(
            self._url(f"/api/v1/tasks/{task_id}"), headers=self._headers()
        )
        resp.raise_for_status()

    def generate_script(self, subject: str, language: str = "id-ID") -> str:
        """POST /api/v1/scripts -> LLM-generated script for a subject."""
        resp = self._client.post(
            self._url("/api/v1/scripts"),
            json={"video_subject": subject, "video_language": language},
            headers=self._headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {}) if isinstance(body, dict) else {}
        return data.get("video_script", "") or ""

    def wait_for_completion(
        self, task_id: str, *, poll_interval: float = 5.0, timeout: float = 1800.0
    ) -> MPTTaskStatus:
        """Poll GET /api/v1/tasks/{id} until terminal or timed out."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.get_task(task_id)
            if status.state in (MPTState.SUCCESS, MPTState.ERROR):
                return status
            time.sleep(poll_interval)
        raise TimeoutError(f"MPT task {task_id} did not finish within {timeout}s")


class MockMPTClient:
    """Stand-in MPT client for local-agent tests without a running MPT."""

    def __init__(self) -> None:
        self._tasks: dict[str, MPTTaskStatus] = {}
        self._counter = 0
        self._scripts: dict[str, str] = {}

    def create_video(self, params: MPTVideoParams) -> str:
        self._counter += 1
        task_id = f"mpt_mock_{self._counter}"
        self._tasks[task_id] = MPTTaskStatus(
            task_id=task_id, state=MPTState.NO_RESULT, progress=0
        )
        self._scripts[task_id] = params.video_script or f"Script untuk {params.video_subject}"
        return task_id

    def get_task(self, task_id: str) -> MPTTaskStatus:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.state == MPTState.SUCCESS:
            return task
        new_progress = min(100, task.progress + 25)
        if new_progress >= 100:
            task = MPTTaskStatus(
                task_id=task_id,
                state=MPTState.SUCCESS,
                progress=100,
                script=self._scripts.get(task_id, ""),
                videos=[f"http://mock.local/tasks/{task_id}/final-1.mp4"],
                combined_videos=[f"http://mock.local/tasks/{task_id}/combined-1.mp4"],
            )
        else:
            task.progress = new_progress
        self._tasks[task_id] = task
        return task

    def delete_task(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)

    def generate_script(self, subject: str, language: str = "id-ID") -> str:
        return f"[mock script] {subject} ({language})"

    def wait_for_completion(
        self, task_id: str, *, poll_interval: float = 0.01, timeout: float = 5.0
    ) -> MPTTaskStatus:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.get_task(task_id)
            if status.state in (MPTState.SUCCESS, MPTState.ERROR):
                return status
            time.sleep(poll_interval)
        raise TimeoutError(f"mock MPT task {task_id} timed out")


