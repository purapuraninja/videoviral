"""Instagram Reels publisher — Instagram Graph API via Facebook Login (free).

Instagram is the awkward one: containers normally require a **publicly reachable
video URL** because Meta cURLs the file. Since our design keeps the video on the
render PC and never exposes it publicly, we use the one path that accepts local
bytes — the resumable upload host ``rupload.facebook.com`` — which Meta documents
as available only to apps using **Facebook Login for Business** with a Page
access token.

Flow:

1. ``POST /{ig_user_id}/media?media_type=REELS&upload_type=resumable`` → returns
   a container id and an ``uri`` to upload to.
2. ``POST {uri}`` with headers ``Authorization: OAuth <token>``, ``offset: 0``,
   ``file_size: <bytes>`` and the raw body.
3. Poll ``GET /{container_id}?fields=status_code`` until ``FINISHED``.
4. ``POST /{ig_user_id}/media_publish?creation_id=<container_id>``.
5. ``GET /{media_id}?fields=permalink`` for the public URL.

If the credentials are absent, we return ``manual_required`` rather than failing —
that is the documented fallback for accounts on Instagram Login, which cannot
upload local bytes at all.

Env vars:

- ``VVF_INSTAGRAM_ACCESS_TOKEN`` — Page/User access token with
  ``instagram_basic`` + ``instagram_content_publish``
- ``VVF_INSTAGRAM_USER_ID`` — the Instagram professional account id
- ``VVF_INSTAGRAM_API_VERSION`` (optional, default ``v24.0``)
- ``VVF_INSTAGRAM_SHARE_TO_FEED`` (optional, default ``1``)
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

_REQUIRED = ("VVF_INSTAGRAM_ACCESS_TOKEN", "VVF_INSTAGRAM_USER_ID")
_CAPTION_LIMIT = 2200
_MAX_BYTES = 300 * 1024 * 1024  # Meta rejects reels larger than 300 MB


class InstagramPublisher:
    """Publishes a local vertical video as an Instagram Reel."""

    platform = Platform.INSTAGRAM_REELS

    def __init__(self, timeout: float = 600.0, poll_seconds: float = 10.0, poll_attempts: int = 30) -> None:
        self._timeout = timeout
        self._poll_seconds = poll_seconds
        self._poll_attempts = poll_attempts

    def is_configured(self) -> bool:
        return not missing_env(*_REQUIRED)

    def publish(self, req: PublishRequestData) -> PublishOutcome:
        missing = missing_env(*_REQUIRED)
        if missing:
            return PublishOutcome.manual(
                self.platform,
                "missing credentials: "
                + ", ".join(missing)
                + " (Instagram Login apps cannot upload local files; use Facebook Login for Business)",
            )
        if not os.path.isfile(req.video_path):
            return PublishOutcome.failed(self.platform, f"file not found: {req.video_path}")

        size = os.path.getsize(req.video_path)
        if size > _MAX_BYTES:
            return PublishOutcome.failed(
                self.platform, f"file is {size} bytes; Instagram rejects reels over {_MAX_BYTES}"
            )

        token = env("VVF_INSTAGRAM_ACCESS_TOKEN")
        ig_user = env("VVF_INSTAGRAM_USER_ID")
        version = env("VVF_INSTAGRAM_API_VERSION", "v24.0")
        graph = f"https://graph.facebook.com/{version}"

        with httpx.Client(timeout=self._timeout) as client:
            # 1. container with a resumable upload session
            try:
                created = client.post(
                    f"{graph}/{ig_user}/media",
                    params={
                        "media_type": "REELS",
                        "upload_type": "resumable",
                        "caption": req.caption(_CAPTION_LIMIT),
                        "share_to_feed": "true"
                        if env("VVF_INSTAGRAM_SHARE_TO_FEED", "1") not in ("0", "false", "no")
                        else "false",
                        "access_token": token,
                    },
                )
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(self.platform, f"container failed: {exc}", retryable=True)
            if created.status_code in (401, 403):
                return PublishOutcome.manual(
                    self.platform,
                    f"container rejected (HTTP {created.status_code}); re-authorize the Page token",
                )
            if created.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"container HTTP {created.status_code}: {_short(created.text)}",
                    retryable=is_retryable_status(created.status_code),
                )
            payload = created.json() or {}
            container_id, upload_uri = payload.get("id"), payload.get("uri")
            if not container_id:
                return PublishOutcome.failed(self.platform, f"no container id: {_short(created.text)}")
            if not upload_uri:
                # No resumable session -> this app is on Instagram Login and needs
                # a hosted URL, which we deliberately do not provide.
                return PublishOutcome.manual(
                    self.platform,
                    "no resumable upload URI returned; this app requires a public video URL",
                )

            # 2. upload local bytes (note: "OAuth" scheme, lowercase headers)
            try:
                with open(req.video_path, "rb") as fh:
                    up = client.post(
                        upload_uri,
                        content=fh,
                        headers={
                            "Authorization": f"OAuth {token}",
                            "offset": "0",
                            "file_size": str(size),
                        },
                    )
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(self.platform, f"upload failed: {exc}", retryable=True)
            if up.status_code >= 400 or not (up.json() or {}).get("success"):
                return PublishOutcome.failed(
                    self.platform,
                    f"upload HTTP {up.status_code}: {_short(up.text)}",
                    retryable=is_retryable_status(up.status_code),
                )

            # 3. wait for Meta to finish transcoding
            ready = self._await_container(client, graph, container_id, token)
            if ready is not None:
                return ready

            # 4. publish
            try:
                pub = client.post(
                    f"{graph}/{ig_user}/media_publish",
                    params={"creation_id": container_id, "access_token": token},
                )
            except httpx.HTTPError as exc:
                return PublishOutcome.failed(self.platform, f"publish failed: {exc}", retryable=True)
            if pub.status_code >= 400:
                return PublishOutcome.failed(
                    self.platform,
                    f"publish HTTP {pub.status_code}: {_short(pub.text)}",
                    retryable=is_retryable_status(pub.status_code),
                )
            media_id = (pub.json() or {}).get("id")
            if not media_id:
                return PublishOutcome.failed(self.platform, f"no media id: {_short(pub.text)}")

            # 5. permalink
            permalink = self._permalink(client, graph, media_id, token)
            if permalink:
                return PublishOutcome.published(self.platform, permalink, media_id)
            return PublishOutcome.published(
                self.platform, f"https://www.instagram.com/reel/{media_id}/", media_id
            )

    # ------------------------------------------------------------------
    def _await_container(
        self, client: httpx.Client, graph: str, container_id: str, token: str
    ) -> PublishOutcome | None:
        """Poll container status. Returns an outcome only if it will not publish."""
        last = ""
        for _ in range(self._poll_attempts):
            try:
                resp = client.get(
                    f"{graph}/{container_id}",
                    params={"fields": "status_code,status", "access_token": token},
                )
            except httpx.HTTPError as exc:
                last = str(exc)
                time.sleep(self._poll_seconds)
                continue
            data = resp.json() if resp.status_code < 400 else {}
            code = (data or {}).get("status_code") or ""
            if code == "FINISHED":
                return None
            if code in ("ERROR", "EXPIRED"):
                return PublishOutcome.failed(
                    self.platform, f"container {code}: {(data or {}).get('status') or 'no detail'}"
                )
            last = code or f"HTTP {resp.status_code}"
            time.sleep(self._poll_seconds)
        return PublishOutcome.failed(
            self.platform, f"container not ready after polling (last: {last or 'unknown'})", retryable=True
        )

    def _permalink(self, client: httpx.Client, graph: str, media_id: str, token: str) -> str | None:
        try:
            resp = client.get(
                f"{graph}/{media_id}", params={"fields": "permalink", "access_token": token}
            )
            if resp.status_code < 400:
                return (resp.json() or {}).get("permalink")
        except httpx.HTTPError:
            pass
        return None


def _short(text: str, limit: int = 300) -> str:
    return (text or "").replace("\n", " ").strip()[:limit]


__all__ = ["InstagramPublisher"]
