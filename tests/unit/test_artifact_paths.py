"""M4 behaviors: metadata-only artifacts + preview serve paths.

Covers the RenderRunner helpers that turn MPT task URLs into (a) a path the
local preview server can serve and (b) an absolute filesystem path for statting
size — without uploading binaries to the VPS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the agent importable in the test env (mirrors tests/conftest.py).
ROOT = Path(__file__).resolve().parents[2]
for rel in ["apps/local-render-agent/src", "integrations/money-printer-turbo/src"]:
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from vvf_local_agent.runner import RenderRunner  # noqa: E402
from vvf_mpt import MockMPTClient  # noqa: E402


def _runner(preview_root: Path) -> RenderRunner:
    os.environ["VVF_PREVIEW_ROOT"] = str(preview_root)
    return RenderRunner(MockMPTClient(), "http://127.0.0.1:8080")


def test_serve_path_strips_mpt_tasks_prefix(tmp_path):
    r = _runner(tmp_path)
    assert r._serve_path("http://127.0.0.1:8080/tasks/abc123/final-1.mp4") == "abc123/final-1.mp4"
    assert r._serve_path("/tasks/abc123/final-1.mp4") == "abc123/final-1.mp4"
    assert r._serve_path("abc123/final-1.mp4") == "abc123/final-1.mp4"


def test_abs_local_path_joins_under_preview_root(tmp_path):
    r = _runner(tmp_path)
    abs_p = r._abs_local_path("abc123/final-1.mp4")
    # Must resolve inside the preview root.
    assert os.path.commonpath([str(tmp_path), abs_p]) == str(tmp_path)
    assert abs_p.endswith(os.path.join("abc123", "final-1.mp4"))


def test_artifacts_never_upload_binary_and_record_local_path(tmp_path):
    """The artifact list carries a servable local path + metadata, never bytes."""
    import types

    r = _runner(tmp_path)

    payload = types.SimpleNamespace(
        job_id="rj_1",
        idempotency_key="idem-1",
        candidate=types.SimpleNamespace(title="t", sources=[]),
        video=types.SimpleNamespace(
            aspect_ratio=types.SimpleNamespace(value="9:16"),
            language=types.SimpleNamespace(value="id-ID"),
        ),
        creative=types.SimpleNamespace(voice="id-ID-ArdiNeural"),
    )
    status = types.SimpleNamespace(
        videos=["http://127.0.0.1:8080/tasks/abc123/final-1.mp4"],
        combined_videos=[],
    )
    artifacts = r._artifacts("script text", payload, "task-x", status)
    by_type = {a.artifact_type: a for a in artifacts}

    mp4 = by_type["mp4"]
    assert mp4.local_path == "abc123/final-1.mp4"
    assert mp4.storage_url == ""  # not uploaded; VPS stores metadata only
    assert mp4.extra["abs_local_path"].endswith(os.path.join("abc123", "final-1.mp4"))
    assert by_type["script"].storage_url.startswith("data:text/plain;base64,")
    assert by_type["provenance"].storage_url.startswith("data:application/json;base64,")
