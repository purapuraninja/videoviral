#!/usr/bin/env bash
# Exercise the manual-fallback publish flow end-to-end against the live API.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

API=http://127.0.0.1:8000/api/v1
U=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
P=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=/tmp/vvf_manual_jar
PSQL="docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c"

curl -s -c "$JAR" -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" -o /dev/null -w 'login:%{http_code}\n'

JOB=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select job_id from publish_targets order by created_at desc limit 1;" | tr -d '[:space:]')
[ -z "$JOB" ] && { echo "no publish targets to test"; exit 0; }
echo "job: $JOB"

echo "=== before ==="
curl -s -b "$JAR" "$API/render-jobs/$JOB/publish-targets" | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    print(f\"  {t['platform']:16} {t['status']:16} url={t['post_url'] or '-'}\")"

TARGET=$(curl -s -b "$JAR" "$API/render-jobs/$JOB/publish-targets" | python3 -c "
import json,sys
rows=[t for t in json.load(sys.stdin) if t['status']!='published']
print(rows[0]['id'] if rows else '')")
[ -z "$TARGET" ] && { echo "nothing left to publish manually"; exit 0; }

echo "=== reject a bad URL (expect 422) ==="
curl -s -o /dev/null -w '  bad-url:%{http_code}\n' -b "$JAR" \
  -X POST "$API/publish-targets/$TARGET/manual" \
  -H 'Content-Type: application/json' -d '{"post_url":"not-a-url"}'

echo "=== record a manual post URL ==="
curl -s -b "$JAR" -X POST "$API/publish-targets/$TARGET/manual" \
  -H 'Content-Type: application/json' \
  -d '{"post_url":"https://www.youtube.com/shorts/manualtest123"}' \
  -w '\n  http:%{http_code}\n' | tail -2

echo "=== after ==="
bash scripts/publish_status.sh "$JOB"

echo "=== event trail ==="
$PSQL "select concat(created_at::text,' | ',status,' | ',message) from render_job_events where job_id='$JOB' order by created_at desc limit 5;"
