"""MPT state -> VVF status mapping + mock task lifecycle."""

from __future__ import annotations

from vvf_contracts import MPTVideoParams, RenderJobPayload, RenderJobStatus
from vvf_contracts.render import JobCandidate, JobCreative, JobVideo
from vvf_mpt import MPTState, MPTTaskStatus, MockMPTClient, map_state_to_vvf_status


def _status(state: int, progress: int = 0) -> MPTTaskStatus:
    return MPTTaskStatus(task_id="t", state=state, progress=progress)


def test_state_mapping():
    assert map_state_to_vvf_status(_status(MPTState.SUCCESS)) == RenderJobStatus.COMPLETED
    assert map_state_to_vvf_status(_status(MPTState.ERROR)) == RenderJobStatus.FAILED
    assert map_state_to_vvf_status(_status(MPTState.IN_PROGRESS, 0)) == RenderJobStatus.SCRIPTING
    assert map_state_to_vvf_status(_status(MPTState.IN_PROGRESS, 5)) == RenderJobStatus.ASSETS
    assert map_state_to_vvf_status(_status(MPTState.IN_PROGRESS, 35)) == RenderJobStatus.TTS
    assert map_state_to_vvf_status(_status(MPTState.IN_PROGRESS, 65)) == RenderJobStatus.RENDERING
    assert map_state_to_vvf_status(_status(MPTState.IN_PROGRESS, 95)) == RenderJobStatus.UPLOADING


def test_mock_mpt_lifecycle_completes():
    client = MockMPTClient()
    payload = RenderJobPayload(
        job_id="rj", idempotency_key="k", candidate=JobCandidate(title="X"),
        video=JobVideo(), creative=JobCreative(),
    )
    params = MPTVideoParams.from_payload(payload)
    task_id = client.create_video(params)
    status = client.wait_for_completion(task_id, poll_interval=0.001, timeout=5)
    assert status.state == MPTState.SUCCESS
    assert status.videos  # final mp4 url present


def test_mock_generate_script():
    client = MockMPTClient()
    assert "mock script" in client.generate_script("sub", "id-ID")
