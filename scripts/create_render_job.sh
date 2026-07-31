#!/usr/bin/env bash
# Create a render job for the newest approved candidate (M4 verification).
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

API=http://127.0.0.1:8000/api/v1
USER=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
PASS=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=/tmp/vvf_job_cookies
PROFILE="${1:-TikTok ID 45s}"

curl -s -c "$JAR" -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}" -o /dev/null -w 'login:%{http_code}\n'

CAND=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select id from content_candidates where status='approved' order by created_at desc limit 1;" | tr -d '[:space:]')

if [ -z "$CAND" ]; then
  echo "No approved candidate found."; exit 1
fi
echo "candidate: $CAND"
echo "profile  : $PROFILE"

curl -s -b "$JAR" -X POST \
  "$API/candidates/$CAND/render-jobs?profile_name=$(printf %s "$PROFILE" | sed 's/ /%20/g')" \
  -w '\nhttp:%{http_code}\n'
