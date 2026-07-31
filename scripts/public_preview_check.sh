#!/usr/bin/env bash
# Verify the preview stream works through the PUBLIC nginx path (what the browser uses),
# including Range seeking. Confirms nginx does not buffer/break the stream.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
JOB="${1:?usage: public_preview_check.sh <job_id>}"
BASE="${2:-https://api.purapuraninja.my.id}"
U=$(grep '^VVF_ADMIN_USERNAME=' .env | cut -d= -f2)
P=$(grep '^VVF_ADMIN_PASSWORD=' .env | cut -d= -f2)
JAR=/tmp/pub_jar

curl -s -c "$JAR" -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" -o /dev/null -w 'login:%{http_code}\n'

echo "=== public Range GET (browser seek path) ==="
curl -s -b "$JAR" -D - -o /dev/null -H 'Range: bytes=1000000-1001023' \
  "$BASE/api/v1/render-jobs/$JOB/preview?type=mp4" \
  | grep -Ei '^(HTTP/|content-range|accept-ranges|content-length)' || true

echo "=== public full GET (first 5MB only, then abort) ==="
curl -s -b "$JAR" --max-time 60 -r 0-5242879 -o /tmp/pub_part.mp4 \
  -w 'status:%{http_code} downloaded:%{size_download} speed:%{speed_download}B/s\n' \
  "$BASE/api/v1/render-jobs/$JOB/preview?type=mp4"
rm -f /tmp/pub_part.mp4

echo "=== unauthenticated request must be rejected ==="
curl -s -o /dev/null -w 'no-auth status:%{http_code} (expect 401)\n' \
  "$BASE/api/v1/render-jobs/$JOB/preview?type=mp4"
