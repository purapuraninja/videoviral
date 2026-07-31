"""MoneyPrinterTurbo VideoParams mapping.

This mirrors the upstream ``VideoParams`` schema from
``app/models/schema.py`` of MoneyPrinterTurbo so the local adapter can map a
VVF ``RenderJobPayload`` into an MPT task request without hand-written JSON.

Reference (MPT 2026, main branch):
- POST /api/v1/videos  -> create task, body is a TaskVideoRequest
- GET  /api/v1/tasks/{id} -> { state, progress, script, videos, combined_videos }
- state: -1 = error, 0 = no result yet, 9 = in progress/queued, 1 = success
- VideoAspect.portrait == "9:16" -> to_resolution() -> (1080, 1920)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from vvf_contracts.render import RenderJobPayload


class MPTVideoAspect(str, Enum):
    """MPT aspect ratios. Portrait == 9:16 == 1080x1920."""

    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    SQUARE = "1:1"


class MPTVideoParams(BaseModel):
    """Subset of MoneyPrinterTurbo ``VideoParams`` we actively control.

    Only fields the VVF pipeline sets are included; MPT applies sensible
    defaults for everything else. Fields map 1:1 to upstream names so the
    adapter can ``model_dump()`` straight into the request body.
    """

    video_subject: str
    video_script: str = ""
    video_terms: str | list[str] | None = None
    video_aspect: MPTVideoAspect = MPTVideoAspect.PORTRAIT
    video_concat_mode: str = "random"
    video_clip_duration: int = 5
    video_clip_speed: float = 1.0
    video_count: int = 1
    video_source: str = "pexels"
    video_language: str = ""
    voice_name: str = ""
    voice_volume: float = 1.0
    voice_rate: float = 1.0
    bgm_type: str = "random"
    bgm_volume: float = 0.2
    subtitle_enabled: bool = True
    subtitle_position: str = "bottom"
    font_name: str = "STHeitiMedium.ttc"
    text_fore_color: str = "#FFFFFF"
    font_size: int = 60
    stroke_color: str = "#000000"
    stroke_width: float = 1.5
    n_threads: int = 2
    paragraph_number: int = 1
    video_script_prompt: str = ""
    custom_system_prompt: str = ""

    @classmethod
    def from_payload(cls, payload: RenderJobPayload, script: str = "") -> "MPTVideoParams":
        """Map an immutable VVF render job payload into MPT VideoParams.

        The hook/tone are folded into ``video_script_prompt`` so MPT's LLM
        receives the creative direction alongside the candidate title.
        """
        v = payload.video
        creative = payload.creative
        aspect = (
            MPTVideoAspect.PORTRAIT
            if v.aspect_ratio.value == "9:16"
            else MPTVideoAspect.LANDSCAPE
        )
        prompt_bits = [b for b in (creative.hook, f"tone: {creative.tone}") if b]
        return cls(
            video_subject=payload.candidate.title,
            video_script=script,
            video_aspect=aspect,
            video_language=v.language.value,
            voice_name=creative.voice,
            video_source=creative.video_source,
            subtitle_position=_subtitle_position(creative.subtitle_style),
            video_script_prompt=" | ".join(prompt_bits),
            custom_system_prompt=creative.music_profile,
        )


def _subtitle_position(style: str) -> str:
    """Map VVF subtitle styles to MPT's accepted positions (top/center/bottom/custom)."""
    s = style.lower()
    if "top" in s:
        return "top"
    if "center" in s or "centre" in s:
        return "center"
    return "bottom"


__all__ = ["MPTVideoAspect", "MPTVideoParams"]
