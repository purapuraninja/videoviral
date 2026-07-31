#!/usr/bin/env bash
# Run alembic inside the api container, tolerating a missing `alembic` binary
# by invoking the module directly.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
CMD="${1:-upgrade head}"

echo "=== installed vvf/alembic packages ==="
docker compose -f docker-compose.prod.yml exec -T api pip list 2>/dev/null | grep -iE 'alembic|vvf' || true

echo "=== alembic $CMD ==="
docker compose -f docker-compose.prod.yml exec -T api \
  bash -lc "cd /app/packages/database && python -m alembic $CMD" 2>&1 | tail -12
