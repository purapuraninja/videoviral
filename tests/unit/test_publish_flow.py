"""M6 publish-flow logic tests (no DB, no network).

Covers the contract validation and the ``_sync_job_status`` decision table that
maps per-platform target states onto the render job's status.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from vvf_contracts.common import Platform, PublishMode, PublishStatus
from vvf_contracts.publish import (
    ManualPublishIn,
    PublishJobPayload,
    PublishRequest,
    PublishResultItem,
)


# --- request validation ----------------------------------------------------


def test_publish_request_defaults_to_all_three_platforms():
    req = PublishRequest()
    assert req.platforms == [
        Platform.YOUTUBE_SHORTS,
        Platform.TIKTOK,
        Platform.INSTAGRAM_REELS,
    ]
    assert req.mode == PublishMode.AUTO
    assert req.private is False


def test_publish_request_dedupes_platforms_and_keeps_order():
    req = PublishRequest(platforms=[Platform.TIKTOK, Platform.TIKTOK, Platform.YOUTUBE_SHORTS])
    assert req.platforms == [Platform.TIKTOK, Platform.YOUTUBE_SHORTS]


def test_publish_request_rejects_empty_platforms():
    with pytest.raises(ValidationError):
        PublishRequest(platforms=[])


def test_manual_publish_requires_http_url():
    ok = ManualPublishIn(post_url="  https://www.tiktok.com/@me/video/123 ")
    assert ok.post_url == "https://www.tiktok.com/@me/video/123"
    with pytest.raises(ValidationError):
        ManualPublishIn(post_url="tiktok.com/@me/video/123")


def test_publish_payload_carries_relative_local_path():
    """The payload references the file on the PC — never a URL or bytes."""
    payload = PublishJobPayload(
        job_id="rj_1",
        target_ids=["pt_1"],
        platforms=[Platform.TIKTOK],
        local_path="task-abc/final-1.mp4",
        title="Judul",
    )
    assert payload.local_path == "task-abc/final-1.mp4"
    dumped = payload.model_dump()
    assert "video" not in dumped or not isinstance(dumped.get("video"), bytes)


def test_publish_result_item_roundtrip():
    item = PublishResultItem(
        platform=Platform.YOUTUBE_SHORTS,
        status=PublishStatus.PUBLISHED,
        post_url="https://www.youtube.com/shorts/abc",
        platform_post_id="abc",
    )
    data = item.model_dump(mode="json")
    assert data["platform"] == "youtube_shorts"
    assert data["status"] == "published"


# --- job status synchronisation -------------------------------------------


class _FakeTarget:
    def __init__(self, status: str) -> None:
        self.status = status


class _FakeJob:
    def __init__(self) -> None:
        self.status = "completed"


class _FakeDb:
    """Minimal stand-in for the Session calls ``_sync_job_status`` makes."""

    def __init__(self, job: _FakeJob, targets: list[_FakeTarget]) -> None:
        self._job = job
        self._targets = targets

    def get(self, _model, _pk):
        return self._job

    def execute(self, _stmt):
        targets = self._targets

        class _Result:
            def scalars(self):
                class _S:
                    def all(self_inner):
                        return targets

                return _S()

        return _Result()


def _sync(statuses: list[str]) -> str:
    from vvf_api.routers.publish import _sync_job_status

    job = _FakeJob()
    db = _FakeDb(job, [_FakeTarget(s) for s in statuses])
    _sync_job_status(db, "rj_1")
    return job.status


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["published", "published", "published"], "published"),
        (["published", "skipped"], "published"),
        # Work still outstanding keeps the job in publishing.
        (["published", "pending"], "publishing"),
        (["publishing", "failed"], "publishing"),
        # Partial success still counts as published; the failed target is visible
        # on its own row so the admin can retry or go manual.
        (["published", "failed"], "published"),
        (["published", "manual_required"], "published"),
        # Nothing succeeded and nothing is pending -> the job failed to publish.
        (["failed", "failed"], "publish_failed"),
        (["manual_required", "failed"], "publish_failed"),
        (["manual_required"], "publish_failed"),
    ],
)
def test_sync_job_status_decision_table(statuses, expected):
    assert _sync(statuses) == expected


def test_sync_job_status_ignores_empty_target_list():
    """No targets means nothing to reconcile — the job keeps its status."""
    assert _sync([]) == "completed"
