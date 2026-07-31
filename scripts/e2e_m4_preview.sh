#!/usr/bin/env bash
# End-to-end M4 check: create a render job for an approved candidate, wait for the
# agent to render it, then verify preview streaming works over Tailscale with Range.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

API=http://127.0.0.1:8000/api/v1
USER=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
PASS=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=/tmp/vvf_m4_cookies

echo "=== login ==="
curl -s -c "$JAR" -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}" \
  -o /dev/null -w 'login:%{http_code}\n'

echo "=== agent status ==="
docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA \
  -c "select name || ' | preview=' || coalesce(nullif(preview_base_url,''),'(none)') || ' | last_hb=' || coalesce(last_heartbeat_at::text,'never') from agents order by name;"

echo "=== pick newest completed job with a previewable artifact ==="
JOB=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select vo.job_id from video_outputs vo join render_jobs rj on rj.id = vo.job_id
   where vo.artifact_type in ('mp4','mp4_combined') and vo.agent_id is not null
   order by vo.created_at desc limit 1;" | tr -d '[:space:]')

if [ -z "$JOB" ]; then
  echo "No previewable artifact yet — run a render first (approve a candidate + create a job)."
  exit 0
fi
echo "job: $JOB"

echo "=== outputs metadata (expect local_path + agent_id, storage_url == local_path) ==="
docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA \
  -c "select artifact_type || ' | local_path=' || coalesce(local_path,'-') || ' | agent=' || coalesce(agent_id,'-') || ' | size=' || coalesce(size_bytes::text,'-') from video_outputs where job_id = '$JOB' order by created_at;"

echo "=== preview: full GET (expect 200) ==="
curl -s -b "$JAR" -o /dev/null -w 'status:%{http_code} type:%{content_type} size:%{size_download}\n' \
  "$API/render-jobs/$JOB/preview?type=mp4"

echo "=== preview: Range GET (expect 206 + Content-Range) ==="
curl -s -b "$JAR" -D - -o /dev/null -H 'Range: bytes=0-1023' \
  "$API/render-jobs/$JOB/preview?type=mp4" | grep -Ei '^(HTTP/|content-range|accept-ranges|content-length)' || true

echo "=== confirm no video files stored on the VPS ==="
find /opt/viral-video-factory -name '*.mp4' -newermt '-30 days' 2>/dev/null | head -5
echo "(empty above = nothing stored on VPS)"
