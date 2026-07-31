#!/usr/bin/env bash
# Dashboard cookie-based check: proves the app-domain rewrite + cookie auth
# works the way the browser does it (no Authorization header, just a cookie).
set -euo pipefail
APP=https://app.purapuraninja.my.id
PW=${1:-526a0886af726327e864f88756596d5ac919a23fed34cf88}
CJ=$(mktemp)

echo "=== LOGIN via app domain ==="
curl -s -c "$CJ" -X POST "$APP/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$PW\"}" \
  | python3 -c 'import sys,json;print("token=",json.load(sys.stdin).get("session_token","NO"))'

echo "=== cookie set? ==="
grep -o 'vvf_session' "$CJ" && echo "yes" || echo "no cookie"

echo "=== CREATE RUN via app domain (cookie auth) ==="
RID=$(curl -s -b "$CJ" -X POST "$APP/api/v1/research-runs" -H 'Content-Type: application/json' \
  -d '{"keyword":"banjir jakarta terkini","language":"id-ID","period_days":7}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id","NO_ID"))')
echo "run=$RID"

echo "=== START ==="
curl -s -b "$CJ" -X POST "$APP/api/v1/research-runs/$RID/start" \
  | python3 -c 'import sys,json;print("status="+json.load(sys.stdin).get("status","?"))'

echo "=== waiting for discovery ==="
for i in $(seq 1 15); do
  ST=$(curl -s -b "$CJ" "$APP/api/v1/research-runs/$RID" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status","?"))')
  echo "  status=$ST"; [ "$ST" = "completed" ] && break; [ "$ST" = "failed" ] && { echo FAIL; exit 1; }; sleep 2
done

echo "=== CANDIDATES ==="
curl -s -b "$CJ" "$APP/api/v1/research-runs/$RID/candidates" \
  | python3 -c 'import sys,json
cs=json.load(sys.stdin);print("count="+str(len(cs)))
for c in cs: print(" ",c["rank"],c["title"],round(c["final_score"],3))'

rm -f "$CJ"
echo "DASH_OK"
