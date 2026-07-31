#!/usr/bin/env bash
# VVF end-to-end check against the public API.
set -euo pipefail
API=https://api.purapuraninja.my.id
PW=${1:-526a0886af726327e864f88756596d5ac919a23fed34cf88}

echo "=== LOGIN ==="
TOKEN=$(curl -s -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$PW\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("session_token","NO_TOKEN"))')
echo "token=$TOKEN"
[ "$TOKEN" != "NO_TOKEN" ] || { echo "LOGIN FAILED"; exit 1; }

echo "=== CREATE RESEARCH RUN ==="
RID=$(curl -s -X POST "$API/api/v1/research-runs" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"gempa bali terkini","language":"id-ID","period_days":7}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id","NO_ID"))')
echo "run=$RID"

echo "=== START ==="
curl -s -X POST "$API/api/v1/research-runs/$RID/start" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;print("status="+json.load(sys.stdin).get("status","?"))'

echo "=== waiting for discovery worker (mock) ==="
for i in $(seq 1 15); do
  ST=$(curl -s "$API/api/v1/research-runs/$RID" -H "Authorization: Bearer $TOKEN" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status","?"))')
  echo "  status=$ST"
  [ "$ST" = "completed" ] && break
  [ "$ST" = "failed" ] && { echo "RUN FAILED"; exit 1; }
  sleep 2
done

echo "=== CANDIDATES ==="
curl -s "$API/api/v1/research-runs/$RID/candidates" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json
cs=json.load(sys.stdin)
print("count="+str(len(cs)))
for c in cs: print(" ", c["rank"], c["title"], round(c["final_score"],3))'

echo "=== RENDER PROFILES ==="
curl -s "$API/api/v1/render-profiles" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json
ps=json.load(sys.stdin)
for p in ps: print(" ", p["name"], p["resolution"], p["duration_seconds"])'

echo "E2E_OK"
