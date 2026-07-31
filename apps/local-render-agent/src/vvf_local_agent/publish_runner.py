"""Publish worker for the local render agent (M6).

Runs on the render PC, where the video file lives. Claims pending publish
targets from the VPS, uploads to each platform with the official free APIs, and
reports the outcomes back. Credentials stay in this process's environment — they
are never sent to the VPS.
"""

from __future__ import annotations

import os

from vvf_contracts.common import PublishMode, PublishStatus
from vvf_contracts.publish import PublishJobPayload, PublishResultItem
from vvf_publishers import PublishRequestData, publish_all
from vvf_shared.logging import get_logger


class PublishRunner:
    """Turns a claimed publish payload into per-platform results."""

    def __init__(self, preview_root: str) -> None:
        # Publish payloads carry a path relative to the preview/tasks root.
        self._root = os.path.abspath(preview_root)
        self._log = get_logger()

    def resolve_path(self, local_path: str) -> str:
        """Absolute path of the video on this PC."""
        if os.path.isabs(local_path):
            return local_path
        return os.path.join(self._root, local_path.replace("/", os.sep))

    def run(self, vps, payload: PublishJobPayload) -> None:
        """Publish to every platform in the payload and report results."""
        video_path = self.resolve_path(payload.local_path)
        if not os.path.isfile(video_path):
            self._log.warning(f"publish: video missing at {video_path}")
            vps.report_publish(
                payload.job_id,
                [
                    PublishResultItem(
                        platform=p,
                        status=PublishStatus.FAILED,
                        error_message=f"video not found on agent: {payload.local_path}",
                    )
                    for p in payload.platforms
                ],
            )
            return

        req = PublishRequestData(
            video_path=video_path,
            title=payload.title,
            description=payload.description,
            hashtags=payload.hashtags,
            private=payload.private,
        )
        mode = payload.mode if isinstance(payload.mode, PublishMode) else PublishMode(payload.mode)
        self._log.info(
            f"publish job {payload.job_id} -> {[p.value for p in payload.platforms]} (mode={mode.value})"
        )

        outcomes = publish_all(list(payload.platforms), req, mode)
        results = [
            PublishResultItem(
                platform=o.platform,
                status=o.status,
                post_url=o.post_url,
                platform_post_id=o.platform_post_id,
                error_message=o.error_message,
            )
            for o in outcomes
        ]
        for o in outcomes:
            self._log.info(
                f"publish {o.platform.value}: {o.status.value}"
                + (f" -> {o.post_url}" if o.post_url else "")
                + (f" ({o.error_message})" if o.error_message else "")
            )
        vps.report_publish(payload.job_id, results)


__all__ = ["PublishRunner"]
