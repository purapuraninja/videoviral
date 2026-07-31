#!/usr/bin/env bash
# Verify M6 publishing on the VPS: schema, routes, and the manual-fallback flow.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

API=http://127.0.0.1:8000/api/v1
PSQL="docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c"
U=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
P=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=/tmp/vvf_m6_jar

echo "=== alembic head ==="
$PSQL "select version_num from alembic_version;"

echo "=== publish_targets columns ==="
$PSQL "select string_agg(column_name, ', ' order by ordinal_position) from information_schema.columns where table_name='publish_targets';"

echo "=== render_job status constraint (must include publishing states) ==="
$PSQL "select pg_get_constraintdef(oid) from pg_constraint where conname like 'render_job_status%';"

echo "=== routes ==="
curl -s http://127.0.0.1:8000/openapi.json > /tmp/m6_openapi.json
python3 - <<'PY'
import json
p = json.load(open("/tmp/m6_openapi.json"))["paths"]
for path in (
    "/api/v1/render-jobs/{job_id}/publish",
    "/api/v1/render-jobs/{job_id}/publish-targets",
    "/api/v1/publish-targets/{target_id}/manual",
    "/api/v1/publish-targets/{target_id}/retry",
    "/api/v1/agents/claim-publish",
    "/api/v1/agents/jobs/{job_id}/publish-result",
):
    print(f"  {'OK ' if path in p else 'MISSING'} {path}")
PY

echo "=== login ==="
curl -s -c "$JAR" -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" -o /dev/null -w '  login:%{http_code}\n'

echo "=== unauthenticated publish must be rejected ==="
curl -s -o /dev/null -w '  no-auth:%{http_code} (expect 401)\n' \
  -X POST "$API/render-jobs/rj_x/publish" -H 'Content-Type: application/json' -d '{}'

JOB=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select vo.job_id from video_outputs vo where vo.artifact_type in ('mp4','mp4_combined') and vo.agent_id is not null order by vo.created_at desc limit 1;" | tr -d '[:space:]')
if [ -z "$JOB" ]; then echo "no publishable job found"; exit 0; fi
echo "=== job: $JOB ==="

echo "=== queue publish targets (auto) ==="
curl -s -b "$JAR" -X POST "$API/render-jobs/$JOB/publish" \
  -H 'Content-Type: application/json' \
  -d '{"platforms":["youtube_shorts","tiktok","instagram_reels"],"mode":"auto","hashtags":["berita","gempa"]}' \
  -w '\n  http:%{http_code}\n' | tail -3

echo "=== targets ==="
$PSQL "select concat(platform,' | ',mode,' | ',status,' | attempt=',attempt) from publish_targets where job_id='$JOB' order by platform;"

echo "=== job status ==="
$PSQL "select status from render_jobs where id='$JOB';"
