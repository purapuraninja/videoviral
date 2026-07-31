#!/usr/bin/env bash
# Isolate: does the PC preview server itself serve a full (non-Range) GET correctly?
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
PATH_ON_PC="${1:?usage: probe_preview_upstream.sh <task_id/final-1.mp4>}"

echo "=== direct from API container -> PC preview server (no Range) ==="
docker compose -f docker-compose.prod.yml exec -T api python - <<PY
import httpx
url = "http://100.96.233.10:8090/${PATH_ON_PC}"
with httpx.Client(timeout=60.0) as c:
    with c.stream("GET", url) as r:
        n = 0
        for chunk in r.iter_bytes(chunk_size=65536):
            n += len(chunk)
        print("no-Range  status:", r.status_code, "| headers CL:", r.headers.get("Content-Length"), "| bytes streamed:", n)

    with c.stream("GET", url, headers={"Range": "bytes=0-1023"}) as r:
        n = sum(len(ch) for ch in r.iter_bytes(chunk_size=65536))
        print("Range     status:", r.status_code, "| Content-Range:", r.headers.get("Content-Range"), "| bytes streamed:", n)
PY
