"""Publisher registry + manual fallback (M6).

``get_publisher`` returns the publisher for a platform. ``publish_all`` runs the
requested platforms in order and always produces one outcome per platform — a
platform that is not configured yields ``manual_required`` instead of an error,
so a partially-configured setup still publishes where it can.
"""

from __future__ import annotations

from vvf_contracts.common import Platform, PublishMode, PublishStatus

from vvf_publishers.base import (
    Publisher,
    PublishOutcome,
    PublishRequestData,
)
from vvf_publishers.instagram import InstagramPublisher
from vvf_publishers.tiktok import TikTokPublisher
from vvf_publishers.youtube import YouTubePublisher


class ManualPublisher:
    """Fallback that never uploads — the admin posts by hand.

    Used when the admin explicitly chooses manual mode. The video stays on the PC
    and is downloadable from the dashboard preview.
    """

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    def is_configured(self) -> bool:
        return True

    def publish(self, req: PublishRequestData) -> PublishOutcome:  # noqa: ARG002
        return PublishOutcome.manual(self.platform, "manual mode: upload by hand and record the URL")


_REGISTRY: dict[Platform, type] = {
    Platform.YOUTUBE_SHORTS: YouTubePublisher,
    Platform.TIKTOK: TikTokPublisher,
    Platform.INSTAGRAM_REELS: InstagramPublisher,
}


def get_publisher(platform: Platform, mode: PublishMode = PublishMode.AUTO) -> Publisher:
    """Return the publisher for ``platform`` (manual mode always returns the stub)."""
    if mode == PublishMode.MANUAL:
        return ManualPublisher(platform)
    cls = _REGISTRY.get(platform)
    if cls is None:
        return ManualPublisher(platform)
    return cls()  # type: ignore[return-value]


def publish_all(
    platforms: list[Platform],
    req: PublishRequestData,
    mode: PublishMode = PublishMode.AUTO,
) -> list[PublishOutcome]:
    """Publish to each platform, returning exactly one outcome per platform."""
    outcomes: list[PublishOutcome] = []
    for platform in platforms:
        publisher = get_publisher(platform, mode)
        try:
            outcomes.append(publisher.publish(req))
        except Exception as exc:  # noqa: BLE001 - a publisher bug must not abort the rest
            outcomes.append(
                PublishOutcome.failed(platform, f"publisher raised {type(exc).__name__}: {exc}")
            )
    return outcomes


__all__ = [
    "InstagramPublisher",
    "ManualPublisher",
    "PublishOutcome",
    "PublishRequestData",
    "PublishStatus",
    "Publisher",
    "TikTokPublisher",
    "YouTubePublisher",
    "get_publisher",
    "publish_all",
]
