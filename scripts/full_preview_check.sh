#!/usr/bin/env bash
# Download the full preview stream to verify the whole file transfers over Tailscale.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
API=http://127.0.0.1:8000/api/v1
JOB="${1:?usage: full_preview_check.sh <job_id>}"
U=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
P=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)

curl -s -c /tmp/fpc_jar -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" -o /dev/null

echo "=== full GET (streams entire file through the VPS, nothing persisted) ==="
curl -s -b /tmp/fpc_jar -o /tmp/fpc_full.mp4 \
  -w 'status:%{http_code} type:%{content_type} downloaded:%{size_download} speed:%{speed_download}B/s\n' \
  "$API/render-jobs/$JOB/preview?type=mp4"

echo "=== expected size from DB ==="
docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA \
  -c "select size_bytes from video_outputs where job_id='$JOB' and artifact_type='mp4' order by created_at desc limit 1;"

echo "=== ffprobe the streamed copy (resolution check) ==="
if command -v ffprobe >/dev/null 2>&1; then
  ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of csv=p=0 /tmp/fpc_full.mp4
else
  echo "(ffprobe not installed on VPS; skipping)"
fi

rm -f /tmp/fpc_full.mp4
echo "=== temp copy removed; VPS stores no video ==="
find /opt/viral-video-factory /tmp -name '*.mp4' 2>/dev/null | head -5
