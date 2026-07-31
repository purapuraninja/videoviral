#!/usr/bin/env bash
# List check constraints on a table (default render_jobs).
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
TABLE="${1:-render_jobs}"
docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select conname || ' => ' || pg_get_constraintdef(oid) from pg_constraint where conrelid = '$TABLE'::regclass and contype = 'c' order by conname;"
