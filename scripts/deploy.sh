#!/usr/bin/env bash
# VVF VPS deploy helper. Run on the VPS from the repo root:
#   bash scripts/deploy.sh
# Idempotent: generates .env once, builds, migrates, seeds, health-checks.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

DATA_DIR="/opt/viral-video-factory/data"
mkdir -p "$DATA_DIR"/{postgres,redis,wigolo}

gen() { openssl rand -hex 24; }

if [ ! -f .env ]; then
  echo "[deploy] generating .env with strong random secrets ..."
  cat > .env <<EOF
VVF_ENV=production
VVF_LOG_LEVEL=INFO
VVF_SECRET_KEY=$(gen)
VVF_ADMIN_USERNAME=admin
VVF_ADMIN_PASSWORD=$(gen)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=vvf
POSTGRES_USER=vvf
POSTGRES_PASSWORD=$(gen)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=$(gen)
REDIS_DB=0
API_HOST=0.0.0.0
API_PORT=8000
VVF_CORS_ORIGINS=https://app.purapuraninja.my.id,https://api.purapuraninja.my.id
NEXT_PUBLIC_API_URL=http://api:8000
WIGOLO_BASE_URL=http://wigolo:3000
WIGOLO_API_TOKEN=
MPT_BASE_URL=http://127.0.0.1:8080
MPT_API_TOKEN=
VVF_WIGOLO_USE_MOCK=1
EOF
  chmod 600 .env
  echo "[deploy] .env created (chmod 600). Admin password:"
  grep VVF_ADMIN_PASSWORD .env
else
  echo "[deploy] .env exists, leaving secrets untouched."
fi

echo "[deploy] building + starting stack ..."
docker compose -f docker-compose.prod.yml up -d --build

echo "[deploy] waiting for API to become healthy ..."
for i in $(seq 1 40); do
  if docker compose -f docker-compose.prod.yml exec -T api python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health',timeout=2); print('ok')" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "[deploy] running migrations ..."
docker compose -f docker-compose.prod.yml exec -T api bash -lc "cd /app/packages/database && alembic upgrade head"

echo "[deploy] seeding admin + render profiles ..."
docker compose -f docker-compose.prod.yml exec -T api python -m vvf_database.seed

echo "[deploy] stack status:"
docker compose -f docker-compose.prod.yml ps

echo
echo "================ DONE ================"
echo "Admin:      $(grep VVF_ADMIN_USERNAME .env | cut -d= -f2) / $(grep VVF_ADMIN_PASSWORD .env | cut -d= -f2)"
echo "Dashboard:  https://app.purapuraninja.my.id"
echo "API docs:   https://api.purapuraninja.my.id/docs"
echo "Local health: curl -s http://127.0.0.1:8000/health"
echo "====================================="
