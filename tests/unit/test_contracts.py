"""Contract sanity checks: enums, defaults, and the render job payload round-trip."""

from __future__ import annotations

from vvf_contracts import (
    AspectRatio,
    CandidateStatus,
    JobCandidate,
    JobCreative,
    JobVideo,
    LanguageCode,
    MPTVideoParams,
    Platform,
    RenderJobPayload,
    RenderJobStatus,
    ResearchRunCreate,
    RiskFlag,
)


def test_aspect_and_language_enums():
    assert AspectRatio.PORTRAIT.value == "9:16"
    assert LanguageCode.INDONESIAN.value == "id-ID"


def test_render_job_status_flow_values():
    flow = ["queued", "claimed", "scripting", "assets", "tts", "subtitles",
            "rendering", "uploading", "completed"]
    for s in flow:
        assert RenderJobStatus(s).value == s


def test_research_run_create_defaults():
    r = ResearchRunCreate(keyword="gempa bali")
    assert r.language == LanguageCode.INDONESIAN
    assert r.period_days == 7
    assert r.keyword == "gempa bali"


def test_render_job_payload_round_trip():
    payload = RenderJobPayload(
        job_id="rj_1",
        idempotency_key="key-1",
        candidate=JobCandidate(title="Topik", facts=["fakta"], sources=[]),
        video=JobVideo(),
        creative=JobCreative(),
    )
    data = payload.model_dump()
    restored = RenderJobPayload(**data)
    assert restored.candidate.title == "Topik"
    assert restored.idempotency_key == "key-1"


def test_mpt_params_from_payload_portrait():
    payload = RenderJobPayload(
        job_id="rj_2",
        idempotency_key="k2",
        candidate=JobCandidate(title="Judul"),
        video=JobVideo(),
        creative=JobCreative(hook="Cek ini!", tone="informative-fast"),
    )
    params = MPTVideoParams.from_payload(payload, script="naskah")
    assert params.video_aspect.value == "9:16"
    assert params.video_language == "id-ID"
    assert params.video_subject == "Judul"
    assert "tone: informative-fast" in params.video_script_prompt
    assert params.video_script == "naskah"


def test_risk_flag_and_platform_values():
    assert Platform.TIKTOK.value == "tiktok"
    assert RiskFlag.VIOLENCE.value == "violence"
    assert CandidateStatus.PROPOSED.value == "proposed"
