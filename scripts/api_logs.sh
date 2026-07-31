#!/usr/bin/env bash
# Dump API container logs (avoids shell-quoting issues when run remotely).
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
docker compose -f docker-compose.prod.yml logs api --tail "${1:-80}" 2>&1
