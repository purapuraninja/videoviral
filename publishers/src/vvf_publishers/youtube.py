"""YouTube Shorts publisher — YouTube Data API v3 (free).

Auth: OAuth 2.0 refresh-token flow. One-time setup creates an OAuth client and
a refresh token with the ``youtube.upload`` scope; the refresh token lives in the
render PC's environment only.

Upload: resumable upload (``uploadType=resumable``) so large files survive a
flaky connection — POST the metadata, receive an upload URL in ``Location``,
then PUT the bytes to that URL.

Env vars:

- ``VVF_YOUTUBE_CLIENT_ID``
- ``VVF_YOUTUBE_CLIENT_SECRET``
- ``VVF_YOUTUBE_REFRESH_TOKEN``
- ``VVF_YOUTUBE_CATEGORY_ID`` (optional, default ``25`` = News & Politics)

Note: projects created after 2020-07-28 that have not passed Google's API audit
have every upload forced to ``private``. That is a platform restriction, not a
bug — the upload still succeeds and the post URL is returned.
"""

from __future__ import annotations

import os

import httpx
from vvf_contracts.common import Platform

from vvf_publishers.base import (
    PublishOutcome,
    PublishRequestData,
    env,
    is_retryable_status,
    missing_env,
)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
_REQUIRED = (
    "VVF_YOUTUBE_CLIENT_ID",
    "VVF_YOUTUBE_CLIENT_SECRET",
    "VVF_YOUTUBE_REFRESH_TOKEN",
)
# YouTube rejects titles > 100 chars and descriptions > 5000 chars.
_TITLE_LIMIT = 100
_DESC_LIMIT = 5000


class YouTubePublisher:
    """Uploads a vertical video as a YouTube Short."""

    platform = Platform.YOUTUBE_SHORTS

    def __init__(self, timeout: float = 600.0) -> None:
        self._timeout = timeout

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

        with httpx.Client(timeout=self._timeout) as client:
            token, err = self._access_token(client)
            if token is None:
                return err  # type: ignore[return-value]

            body = {
                "snippet": {
                    "title": (req.title or "Video")[:_TITLE_LIMIT],
                    "description": req.caption(_DESC_LIMIT),
                    "tags": [t.lstrip("#") for t in req.hashtags][:15],
                    "categoryId": env("VVF_YOUTUBE_CATEGORY_ID", "25"),
                },
                "status": {
                    "privacyStatus": "private" if req.private else "public",
                    "selfDeclaredMadeForKids": False,
                    # Required disclosure: the video is AI-generated.
                    "containsSyntheticMedia": True,
                },
            }
            size = os.path.getsize(req.video_path)
            try:
                init = client.post(
                    _UPLOAD_URL,
                    params={"uploadType": "resumable", "part": "snippet,status"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/mp4",
                        "X-Upload-Content-Length": str(size),
                    },
                    json=body,
                )
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(self.platform, f"init failed: {exc}", retryable=True)

            if init.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"init HTTP {init.status_code}: {_short(init.text)}",
                    retryable=is_retryable_status(init.status_code),
                )
            session_url = init.headers.get("Location") or init.headers.get("location")
            if not session_url:
                return PublishOutcome.failed(self.platform, "no resumable session URL returned")

            try:
                with open(req.video_path, "rb") as fh:
                    up = client.put(
                        session_url,
                        content=fh,
                        headers={"Content-Type": "video/mp4", "Content-Length": str(size)},
                    )
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(
                    self.platform, f"upload failed: {exc}", retryable=True
                )

            if up.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"upload HTTP {up.status_code}: {_short(up.text)}",
                    retryable=is_retryable_status(up.status_code),
                )

            video_id = (up.json() or {}).get("id")
            if not video_id:
                return PublishOutcome.failed(self.platform, "upload succeeded but no video id")
            return PublishOutcome.published(
                self.platform, f"https://www.youtube.com/shorts/{video_id}", video_id
            )

    # ------------------------------------------------------------------
    def _access_token(self, client: httpx.Client) -> tuple[str | None, PublishOutcome | None]:
        """Exchange the refresh token for a short-lived access token."""
        try:
            resp = client.post(
                _TOKEN_URL,
                data={
                    "client_id": env("VVF_YOUTUBE_CLIENT_ID"),
                    "client_secret": env("VVF_YOUTUBE_CLIENT_SECRET"),
                    "refresh_token": env("VVF_YOUTUBE_REFRESH_TOKEN"),
                    "grant_type": "refresh_token",
                },
            )
        except httpx.HTTPError as exc:
            return None, PublishOutcome.failed(
                self.platform, f"token request failed: {exc}", retryable=True
            )
        if resp.status_code >= 400:
            # An invalid/revoked refresh token needs human action -> manual.
            return None, PublishOutcome.manual(
                self.platform, f"OAuth refresh failed (HTTP {resp.status_code}); re-authorize"
            )
        token = (resp.json() or {}).get("access_token")
        if not token:
            return None, PublishOutcome.manual(self.platform, "OAuth response had no access_token")
        return token, None


def _short(text: str, limit: int = 300) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:limit]


__all__ = ["YouTubePublisher"]
