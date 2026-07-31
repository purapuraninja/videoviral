#!/usr/bin/env bash
set -euo pipefail
APP=https://app.purapuraninja.my.id
PW=${1:-526a0886af726327e864f88756596d5ac919a23fed34cf88}
CJ=$(mktemp)

curl -s -c "$CJ" -X POST "$APP/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$PW\"}" >/dev/null

echo "=== GET /render-jobs ==="
curl -s -b "$CJ" "$APP/api/v1/render-jobs" | python3 -c 'import sys,json
js=json.load(sys.stdin);print("count="+str(len(js)))
for j in js: print(" ",j["id"],j["status"],j["attempt"])'

JID=$(curl -s -b "$CJ" "$APP/api/v1/render-jobs" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d[0]["id"] if d else "")')
[ -n "$JID" ] || { echo "no jobs"; exit 0; }
echo "=== first job: $JID ==="

echo "=== GET /render-jobs/{id} ==="
curl -s -b "$CJ" "$APP/api/v1/render-jobs/$JID" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("status="+d["status"],"attempt="+str(d["attempt"]))'

echo "=== GET /render-jobs/{id}/events ==="
curl -s -b "$CJ" "$APP/api/v1/render-jobs/$JID/events" | python3 -c 'import sys,json
e=json.load(sys.stdin);print("events="+str(len(e)))
for x in e: print(" ",x["status"],x["message"],str(x["progress"])+"%")'

echo "=== GET /render-jobs/{id}/outputs ==="
curl -s -b "$CJ" "$APP/api/v1/render-jobs/$JID/outputs" | python3 -c 'import sys,json
o=json.load(sys.stdin);print("outputs="+str(len(o)))
for x in o: print(" ",x["artifact_type"],x["storage_url"][:45])'

rm -f "$CJ"
echo JOBS_OK
