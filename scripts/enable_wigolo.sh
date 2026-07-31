#!/usr/bin/env bash
# Enable the live wigolo daemon and verify it end-to-end.
#
# Idempotent: adds any missing WIGOLO_* keys to .env (generating a shared token),
# flips VVF_WIGOLO_USE_MOCK=0, starts the wigolo profile, waits for /health, then
# runs a real keyword search through the adapter.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

COMPOSE="docker compose -f docker-compose.prod.yml"

# --- 1. ensure the shared token + settings exist in .env --------------------
if ! grep -q '^WIGOLO_API_TOKEN=..' .env 2>/dev/null; then
  TOKEN="$(openssl rand -hex 32)"
  echo "[wigolo] generating WIGOLO_API_TOKEN"
  sed -i '/^WIGOLO_API_TOKEN=/d;/^VVF_WIGOLO_API_TOKEN=/d' .env
  printf 'WIGOLO_API_TOKEN=%s\nVVF_WIGOLO_API_TOKEN=%s\n' "$TOKEN" "$TOKEN" >> .env
fi
grep -q '^VVF_WIGOLO_BASE_URL=' .env || echo 'VVF_WIGOLO_BASE_URL=http://wigolo:3333' >> .env
grep -q '^VVF_WIGOLO_CATEGORY=' .env  || echo 'VVF_WIGOLO_CATEGORY=news' >> .env
grep -q '^VVF_WIGOLO_TIME_RANGE=' .env || echo 'VVF_WIGOLO_TIME_RANGE=week' >> .env

echo "[wigolo] setting VVF_WIGOLO_USE_MOCK=0"
if grep -q '^VVF_WIGOLO_USE_MOCK=' .env; then
  sed -i 's/^VVF_WIGOLO_USE_MOCK=.*/VVF_WIGOLO_USE_MOCK=0/' .env
else
  echo 'VVF_WIGOLO_USE_MOCK=0' >> .env
fi

mkdir -p /opt/viral-video-factory/data/wigolo

# --- 2. start the daemon ---------------------------------------------------
echo "[wigolo] starting the wigolo profile (first boot downloads models, be patient)"
$COMPOSE --profile wigolo up -d wigolo

echo "[wigolo] waiting for /health ..."
for i in $(seq 1 60); do
  if $COMPOSE --profile wigolo exec -T wigolo \
      node -e "fetch('http://127.0.0.1:3333/health').then(r=>r.json()).then(j=>{console.log(JSON.stringify(j));process.exit(j.status?0:1)}).catch(()=>process.exit(1))" 2>/dev/null; then
    break
  fi
  sleep 5
done

# --- 3. restart the worker so it picks up the new env ----------------------
echo "[wigolo] recreating discovery-worker with live wigolo"
$COMPOSE up -d --force-recreate discovery-worker

# --- 4. verify the adapter can actually search ----------------------------
echo "[wigolo] live search through the VVF adapter ..."
$COMPOSE exec -T discovery-worker python - <<'PY'
from vvf_wigolo import WigoloClient, WigoloError

client = WigoloClient()
try:
    print("health:", client.health())
except WigoloError as exc:
    raise SystemExit(f"FAIL health: {exc}")

try:
    result = client.search(
        ["gempa bumi terkini", "gempa hari ini indonesia"], language="id-ID", limit=5
    )
except WigoloError as exc:
    raise SystemExit(f"FAIL search: {exc}")

print("engines_used:", result.engines_used)
print("degraded:", result.degraded_backends)
print(f"hits: {len(result.hits)}")
for hit in result.hits[:5]:
    print(f"  - [{hit.score}] {hit.title[:70]}")
    print(f"    {hit.url}")
    print(f"    publisher={hit.publisher} published_at={hit.published_at}")
if not result.hits:
    raise SystemExit("FAIL: live wigolo returned no hits")
print("LIVE WIGOLO OK")
PY

echo "[wigolo] worker log tail:"
$COMPOSE logs discovery-worker --tail 15 2>&1 | tail -15
