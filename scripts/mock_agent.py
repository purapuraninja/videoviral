"""Mock local render agent — drains queued render jobs for a quick demo.

Speaks the real /api/v1/agents/* protocol: register -> heartbeat -> claim-job ->
post stage events -> complete with (fake) artifacts + provenance. Produces NO
real video; it only proves the queue -> claim -> render -> complete loop works.
Run inside the api container: BASE=http://localhost:8000 .
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time

import httpx

BASE = os.getenv("MOCK_AGENT_BASE", "http://localhost:8000")
NAME = os.getenv("MOCK_AGENT_NAME", "mock-agent")

c = httpx.Client(timeout=30.0)

reg = c.post(
    f"{BASE}/api/v1/agents/register",
    json={
        "name": NAME,
        "version": "0.1.0",
        "capabilities": ["mpt", "edge_tts", "whisper"],
        "mpt_base_url": "http://127.0.0.1:8080",
        "available_disk_gb": 100.0,
    },
)
reg.raise_for_status()
rd = reg.json()
agent_id = rd["agent_id"]
token = rd["token"]
H = {"Authorization": f"Bearer {token}"}
print("registered agent", agent_id, flush=True)

STAGES = [
    ("scripting", "generating script", 5),
    ("assets", "collecting footage", 15),
    ("tts", "synthesizing voice", 25),
    ("subtitles", "aligning subtitles", 40),
    ("rendering", "composing video", 65),
    ("uploading", "uploading artifacts", 90),
]


def claim():
    r = c.post(
        f"{BASE}/api/v1/agents/claim-job",
        json={"agent_id": agent_id, "idempotency_key": None},
        headers=H,
    )
    r.raise_for_status()
    return r.json()


def b64(text: str, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(text.encode()).decode()}"


processed = 0
while True:
    job = claim()
    if not job.get("claimed"):
        print("no more queued jobs")
        break
    jid = job["job_id"]
    payload = job.get("payload") or {}
    cand = payload.get("candidate") or {}
    title = cand.get("title", "Untitled")
    print(f"claimed {jid} (attempt {job['attempt']}) -> {title}", flush=True)

    c.post(
        f"{BASE}/api/v1/agents/heartbeat",
        json={
            "agent_id": agent_id,
            "available_disk_gb": 100.0,
            "mpt_healthy": True,
            "active_job_id": jid,
        },
    )

    for st, msg, prog in STAGES:
        c.post(
            f"{BASE}/api/v1/agents/jobs/{jid}/events",
            json={"agent_id": agent_id, "status": st, "message": msg, "progress": prog},
            headers=H,
        )
        time.sleep(0.3)

    script = f"[mock script] {title}"
    prov = {
        "job_id": jid,
        "idempotency_key": payload.get("idempotency_key", ""),
        "mpt_task_id": "mock-task",
        "candidate_title": title,
        "sources": cand.get("sources", []),
        "script": script,
        "video_outputs": [f"http://mock.local/tasks/{jid}/final-1.mp4"],
        "mock": True,
    }
    complete = {
        "agent_id": agent_id,
        "artifacts": [
            {
                "artifact_type": "mp4",
                "storage_url": f"http://mock.local/tasks/{jid}/final-1.mp4",
                "size_bytes": 1234567,
                "duration_seconds": float(payload.get("video", {}).get("duration_seconds", 45)),
            },
            {"artifact_type": "script", "storage_url": b64(script, "text/plain")},
            {"artifact_type": "provenance", "storage_url": b64(json.dumps(prov), "application/json")},
        ],
        "provenance": prov,
        "final_script": script,
        "duration_seconds": 45.0,
    }
    rr = c.post(
        f"{BASE}/api/v1/agents/jobs/{jid}/complete",
        json=complete,
        headers=H,
    )
    print(f"  complete -> {rr.status_code} {rr.text[:120]}", flush=True)
    processed += 1

print(f"DONE, processed {processed} job(s)")
sys.exit(0)
