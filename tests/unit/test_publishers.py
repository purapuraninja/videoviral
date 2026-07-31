"""M6 publisher tests.

These cover the logic we own — credential gating, caption/limit handling, chunk
maths, privacy negotiation, retry classification, and the guarantee that
``publish_all`` always returns one outcome per platform and never raises.
No network calls are made.
"""

from __future__ import annotations

import os

import pytest
from vvf_contracts.common import Platform, PublishMode, PublishStatus
from vvf_publishers import (
    InstagramPublisher,
    ManualPublisher,
    PublishRequestData,
    TikTokPublisher,
    YouTubePublisher,
    get_publisher,
    publish_all,
)
from vvf_publishers.base import is_retryable_status, missing_env
from vvf_publishers.tiktok import _chunking, _pick_privacy

_ALL_CRED_VARS = (
    "VVF_YOUTUBE_CLIENT_ID",
    "VVF_YOUTUBE_CLIENT_SECRET",
    "VVF_YOUTUBE_REFRESH_TOKEN",
    "VVF_TIKTOK_ACCESS_TOKEN",
    "VVF_INSTAGRAM_ACCESS_TOKEN",
    "VVF_INSTAGRAM_USER_ID",
)


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    """Every test runs with a clean, credential-free environment."""
    for name in _ALL_CRED_VARS:
        monkeypatch.delenv(name, raising=False)


# --- caption handling ------------------------------------------------------


def test_caption_appends_hashtags_and_normalises_hash():
    req = PublishRequestData(
        video_path="x.mp4", title="T", description="Gempa Bali", hashtags=["bali", "#gempa"]
    )
    assert req.caption() == "Gempa Bali #bali #gempa"


def test_caption_truncates_to_limit():
    req = PublishRequestData(video_path="x.mp4", title="T", description="a" * 50)
    out = req.caption(20)
    assert len(out) == 20
    assert out.endswith("…")


def test_caption_handles_empty_description():
    req = PublishRequestData(video_path="x.mp4", title="T", hashtags=["fyp"])
    assert req.caption() == "#fyp"


# --- credential gating -> manual_required ---------------------------------


@pytest.mark.parametrize(
    "publisher_cls,platform",
    [
        (YouTubePublisher, Platform.YOUTUBE_SHORTS),
        (TikTokPublisher, Platform.TIKTOK),
        (InstagramPublisher, Platform.INSTAGRAM_REELS),
    ],
)
def test_missing_credentials_yields_manual_required(publisher_cls, platform):
    pub = publisher_cls()
    assert pub.is_configured() is False
    outcome = pub.publish(PublishRequestData(video_path="whatever.mp4", title="T"))
    assert outcome.platform == platform
    assert outcome.status == PublishStatus.MANUAL_REQUIRED
    assert "missing credentials" in (outcome.error_message or "")


def test_configured_when_all_env_present(monkeypatch):
    monkeypatch.setenv("VVF_YOUTUBE_CLIENT_ID", "id")
    monkeypatch.setenv("VVF_YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("VVF_YOUTUBE_REFRESH_TOKEN", "refresh")
    assert YouTubePublisher().is_configured() is True
    assert missing_env("VVF_YOUTUBE_CLIENT_ID") == []


def test_missing_file_is_failure_not_manual(monkeypatch, tmp_path):
    """With credentials present, a missing file is a real failure."""
    monkeypatch.setenv("VVF_TIKTOK_ACCESS_TOKEN", "tok")
    outcome = TikTokPublisher().publish(
        PublishRequestData(video_path=str(tmp_path / "gone.mp4"), title="T")
    )
    assert outcome.status == PublishStatus.FAILED
    assert "file not found" in (outcome.error_message or "")


# --- TikTok chunking + privacy negotiation --------------------------------


def test_single_chunk_for_typical_render():
    """A ~31 MB render fits TikTok's 64 MB single-chunk ceiling."""
    size = 31_247_442
    chunk_size, count = _chunking(size)
    assert (chunk_size, count) == (size, 1)


def test_multi_chunk_for_large_file():
    size = 200 * 1024 * 1024
    chunk_size, count = _chunking(size)
    assert chunk_size == 32 * 1024 * 1024
    assert count == size // chunk_size
    assert count >= 1


def test_privacy_prefers_requested_when_allowed():
    assert (
        _pick_privacy("PUBLIC_TO_EVERYONE", ["PUBLIC_TO_EVERYONE", "SELF_ONLY"], False)
        == "PUBLIC_TO_EVERYONE"
    )


def test_privacy_downgrades_when_not_allowed():
    """Unaudited apps only get SELF_ONLY; we must not send a disallowed level."""
    assert _pick_privacy("PUBLIC_TO_EVERYONE", ["SELF_ONLY"], False) == "SELF_ONLY"


def test_privacy_defaults_to_self_only_when_no_options():
    assert _pick_privacy("PUBLIC_TO_EVERYONE", [], False) == "SELF_ONLY"


def test_privacy_honours_private_request():
    assert (
        _pick_privacy("PUBLIC_TO_EVERYONE", ["PUBLIC_TO_EVERYONE", "SELF_ONLY"], True)
        == "SELF_ONLY"
    )


# --- retry classification -------------------------------------------------


@pytest.mark.parametrize("code,expected", [(429, True), (500, True), (503, True), (400, False), (403, False), (404, False)])
def test_retryable_status_classification(code, expected):
    assert is_retryable_status(code) is expected


# --- registry + publish_all ----------------------------------------------


def test_manual_mode_never_uploads():
    pub = get_publisher(Platform.YOUTUBE_SHORTS, PublishMode.MANUAL)
    assert isinstance(pub, ManualPublisher)
    outcome = pub.publish(PublishRequestData(video_path="x.mp4", title="T"))
    assert outcome.status == PublishStatus.MANUAL_REQUIRED


def test_publish_all_returns_one_outcome_per_platform():
    platforms = [Platform.YOUTUBE_SHORTS, Platform.TIKTOK, Platform.INSTAGRAM_REELS]
    outcomes = publish_all(platforms, PublishRequestData(video_path="x.mp4", title="T"))
    assert [o.platform for o in outcomes] == platforms
    assert all(o.status == PublishStatus.MANUAL_REQUIRED for o in outcomes)


def test_publish_all_survives_a_broken_publisher(monkeypatch):
    """A publisher that raises must not abort the remaining platforms."""

    class Boom:
        platform = Platform.TIKTOK

        def is_configured(self):
            return True

        def publish(self, req):
            raise RuntimeError("kaboom")

    monkeypatch.setattr("vvf_publishers._REGISTRY", {Platform.TIKTOK: Boom})
    outcomes = publish_all(
        [Platform.TIKTOK, Platform.YOUTUBE_SHORTS], PublishRequestData(video_path="x.mp4", title="T")
    )
    assert outcomes[0].status == PublishStatus.FAILED
    assert "kaboom" in (outcomes[0].error_message or "")
    assert outcomes[1].platform == Platform.YOUTUBE_SHORTS


def test_outcomes_never_leak_credentials(monkeypatch, tmp_path):
    """An outcome must not echo a token back to the VPS."""
    monkeypatch.setenv("VVF_TIKTOK_ACCESS_TOKEN", "super-secret-token")
    outcome = TikTokPublisher().publish(
        PublishRequestData(video_path=str(tmp_path / "missing.mp4"), title="T")
    )
    assert "super-secret-token" not in repr(outcome)
