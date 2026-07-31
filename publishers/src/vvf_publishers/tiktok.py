"""TikTok publisher — Content Posting API, Direct Post with ``FILE_UPLOAD`` (free).

Local bytes are fully supported: initialise the post, then ``PUT`` the file to the
returned ``upload_url``. Our renders are ~30 MB, well under the 64 MB single-chunk
ceiling, so a single chunk is used (multi-chunk is handled for larger files).

Mandatory pre-flight: the Creator Info query returns the privacy levels and
interaction toggles the account actually allows. Sending a ``privacy_level`` that
is not in ``privacy_level_options`` is a TOS violation and fails with
``privacy_level_option_mismatch``.

Unaudited apps may only post ``SELF_ONLY``, and TikTok only returns a public post
id for public, moderation-passed posts. When no post id can be obtained we report
``published`` with the profile URL if we know the username, otherwise
``manual_required`` so the admin records the real URL.

Env vars:

- ``VVF_TIKTOK_ACCESS_TOKEN`` — user access token with scope ``video.publish``
- ``VVF_TIKTOK_PRIVACY_LEVEL`` (optional) — preferred level, default
  ``PUBLIC_TO_EVERYONE``; automatically downgraded to an allowed option
"""

from __future__ import annotations

import os
import time

import httpx
from vvf_contracts.common import Platform

from vvf_publishers.base import (
    PublishOutcome,
    PublishRequestData,
    env,
    is_retryable_status,
    missing_env,
)

_BASE = "https://open.tiktokapis.com/v2"
_CREATOR_INFO = f"{_BASE}/post/publish/creator_info/query/"
_INIT = f"{_BASE}/post/publish/video/init/"
_STATUS = f"{_BASE}/post/publish/status/fetch/"
_REQUIRED = ("VVF_TIKTOK_ACCESS_TOKEN",)

_TITLE_LIMIT = 2200
_MAX_SINGLE_CHUNK = 64 * 1024 * 1024  # single chunk is legal up to 64 MB
_CHUNK = 32 * 1024 * 1024  # used when the file needs splitting
_TERMINAL_OK = "PUBLISH_COMPLETE"


class TikTokPublisher:
    """Direct-posts a local video file to TikTok."""

    platform = Platform.TIKTOK

    def __init__(self, timeout: float = 600.0, poll_seconds: float = 5.0, poll_attempts: int = 24) -> None:
        self._timeout = timeout
        self._poll_seconds = poll_seconds
        self._poll_attempts = poll_attempts

    def is_configured(self) -> bool:
        return not missing_env(*_REQUIRED)

    def publish(self, req: PublishRequestData) -> PublishOutcome:
        missing = missing_env(*_REQUIRED)
        if missing:
            return PublishOutcome.manual(
                self.platform, f"missing credentials: {', '.join(missing)}"
            )
        if not os.path.isfile(req.video_path):
            return PublishOutcome.failed(self.platform, f"file not found: {req.video_path}")

        token = env("VVF_TIKTOK_ACCESS_TOKEN")
        auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
        size = os.path.getsize(req.video_path)

        with httpx.Client(timeout=self._timeout) as client:
            info, outcome = self._creator_info(client, auth)
            if info is None:
                return outcome  # type: ignore[return-value]

            privacy = _pick_privacy(
                env("VVF_TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE"),
                info.get("privacy_level_options") or [],
                req.private,
            )
            if privacy is None:
                return PublishOutcome.manual(
                    self.platform, "account allows no usable privacy_level for API posting"
                )

            chunk_size, chunk_count = _chunking(size)
            body = {
                "post_info": {
                    "title": req.caption(_TITLE_LIMIT) or (req.title or "")[:_TITLE_LIMIT],
                    "privacy_level": privacy,
                    "disable_comment": bool(info.get("comment_disabled")),
                    "disable_duet": bool(info.get("duet_disabled")),
                    "disable_stitch": bool(info.get("stitch_disabled")),
                    # Required disclosure: the video is AI-generated.
                    "is_aigc": True,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": chunk_count,
                },
            }

            try:
                init = client.post(_INIT, headers=auth, json=body)
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(self.platform, f"init failed: {exc}", retryable=True)
            if init.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"init HTTP {init.status_code}: {_short(init.text)}",
                    retryable=is_retryable_status(init.status_code),
                )
            data = (init.json() or {}).get("data") or {}
            publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
            if not publish_id or not upload_url:
                return PublishOutcome.failed(self.platform, f"init response incomplete: {_short(init.text)}")

            up_outcome = self._upload(client, upload_url, req.video_path, size, chunk_size, chunk_count)
            if up_outcome is not None:
                return up_outcome

            return self._await_publish(client, auth, publish_id, info.get("creator_username"))

    # ------------------------------------------------------------------
    def _creator_info(
        self, client: httpx.Client, auth: dict[str, str]
    ) -> tuple[dict | None, PublishOutcome | None]:
        """Query allowed privacy levels + toggles (mandatory before posting)."""
        try:
            resp = client.post(_CREATOR_INFO, headers=auth, json={})
        except httpx.HTTPError as exc:
            return None, PublishOutcome.failed(
                self.platform, f"creator_info failed: {exc}", retryable=True
            )
        if resp.status_code in (401, 403):
            return None, PublishOutcome.manual(
                self.platform,
                f"creator_info rejected (HTTP {resp.status_code}); re-authorize or await app audit",
            )
        if resp.status_code >= 400:
            return None, PublishOutcome.failed(
                self.platform,
                f"creator_info HTTP {resp.status_code}: {_short(resp.text)}",
                retryable=is_retryable_status(resp.status_code),
            )
        return (resp.json() or {}).get("data") or {}, None

    def _upload(
        self,
        client: httpx.Client,
        upload_url: str,
        path: str,
        size: int,
        chunk_size: int,
        chunk_count: int,
    ) -> PublishOutcome | None:
        """PUT the bytes. Returns an outcome only on failure."""
        try:
            with open(path, "rb") as fh:
                for index in range(chunk_count):
                    start = index * chunk_size
                    # The final chunk absorbs any trailing bytes.
                    length = size - start if index == chunk_count - 1 else chunk_size
                    fh.seek(start)
                    payload = fh.read(length)
                    end = start + len(payload) - 1  # Content-Range end is inclusive
                    resp = client.put(
                        upload_url,
                        content=payload,
                        headers={
                            "Content-Type": "video/mp4",
                            "Content-Length": str(len(payload)),
                            "Content-Range": f"bytes {start}-{end}/{size}",
                        },
                    )
                    if resp.status_code >= 400:
                        return PublishOutcome.failed(
                            self.platform,
                            f"chunk {index + 1}/{chunk_count} HTTP {resp.status_code}: {_short(resp.text)}",
                            retryable=is_retryable_status(resp.status_code),
                        )
        except httpx.HTTPError as exc:
            return PublishOutcome.failed(self.platform, f"upload failed: {exc}", retryable=True)
        except OSError as exc:
            return PublishOutcome.failed(self.platform, f"read failed: {exc}")
        return None

    def _await_publish(
        self, client: httpx.Client, auth: dict[str, str], publish_id: str, username: str | None
    ) -> PublishOutcome:
        """Poll until TikTok finishes processing, then resolve the post URL."""
        last = ""
        for _ in range(self._poll_attempts):
            try:
                resp = client.post(_STATUS, headers=auth, json={"publish_id": publish_id})
            except httpx.HTTPError as exc:
                last = str(exc)
                time.sleep(self._poll_seconds)
                continue
            if resp.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"status HTTP {resp.status_code}: {_short(resp.text)}",
                    retryable=is_retryable_status(resp.status_code),
                )
            data = (resp.json() or {}).get("data") or {}
            state = data.get("status") or ""
            if state == "FAILED":
                return PublishOutcome.failed(
                    self.platform, f"TikTok rejected the video: {data.get('fail_reason') or 'unknown'}"
                )
            if state == _TERMINAL_OK:
                # Field name is misspelled in TikTok's API; only set for public posts.
                ids = data.get("publicaly_available_post_id") or data.get(
                    "publicly_available_post_id"
                ) or []
                post_id = str(ids[0]) if ids else None
                if post_id and username:
                    return PublishOutcome.published(
                        self.platform, f"https://www.tiktok.com/@{username}/video/{post_id}", post_id
                    )
                if username:
                    # Posted, but TikTok withholds the id (private/unaudited or
                    # still in moderation) — point at the profile.
                    return PublishOutcome.published(
                        self.platform, f"https://www.tiktok.com/@{username}", post_id
                    )
                return PublishOutcome.manual(
                    self.platform, "posted, but TikTok returned no public post id — record the URL manually"
                )
            last = state
            time.sleep(self._poll_seconds)
        return PublishOutcome.failed(
            self.platform, f"still processing after polling (last status: {last or 'unknown'})", retryable=True
        )


def _chunking(size: int) -> tuple[int, int]:
    """Chunk size + count. Single chunk while the file fits TikTok's 64 MB limit."""
    if size <= _MAX_SINGLE_CHUNK:
        return size, 1
    count = size // _CHUNK
    return _CHUNK, max(1, count)


def _pick_privacy(preferred: str, allowed: list[str], force_private: bool) -> str | None:
    """Choose a privacy level the account actually permits."""
    if not allowed:
        # No options reported (e.g. unaudited client) — the only safe choice.
        return "SELF_ONLY"
    if force_private:
        return "SELF_ONLY" if "SELF_ONLY" in allowed else allowed[0]
    if preferred in allowed:
        return preferred
    for fallback in ("PUBLIC_TO_EVERYONE", "FOLLOWER_OF_CREATOR", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"):
        if fallback in allowed:
            return fallback
    return allowed[0]


def _short(text: str, limit: int = 300) -> str:
    return (text or "").replace("\n", " ").strip()[:limit]


__all__ = ["TikTokPublisher"]
