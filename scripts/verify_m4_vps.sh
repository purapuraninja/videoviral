#!/usr/bin/env bash
# Verify M4 deployment on the VPS: schema columns, API routes, health.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf

echo "=== health ==="
curl -s -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:8000/health

echo "=== new DB columns (expect 2 rows) ==="
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U vvf -d vvf -tA -c "
    select table_name||'.'||column_name
    from information_schema.columns
    where (table_name='agents' and column_name='preview_base_url')
       or (table_name='video_outputs' and column_name='agent_id')
    order by 1;"

echo "=== alembic head ==="
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U vvf -d vvf -tA -c "select version_num from alembic_version;"

echo "=== API routes ==="
curl -s http://127.0.0.1:8000/openapi.json > /tmp/openapi.json
python3 - <<'PY'
import json
p = json.load(open("/tmp/openapi.json"))["paths"]
print("preview endpoint present :", "/api/v1/render-jobs/{job_id}/preview" in p)
print("artifact upload removed  :", "/api/v1/agents/jobs/{job_id}/artifact" not in p)
print("outputs endpoint present :", "/api/v1/render-jobs/{job_id}/outputs" in p)
PY

echo "=== registered agents (name / preview_base_url) ==="
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U vvf -d vvf -tA -c "select name||' | preview='||coalesce(nullif(preview_base_url,''),'(none)') from agents;"

echo "=== reachability: VPS api container -> PC preview server ==="
docker compose -f docker-compose.prod.yml exec -T api python -c "
import urllib.request, urllib.error
try:
    r = urllib.request.urlopen('http://100.96.233.10:8090/', timeout=6)
    print('PC preview reachable, HTTP', r.status)
except urllib.error.HTTPError as e:
    print('PC preview reachable, HTTP', e.code)
except Exception as e:
    print('PC preview NOT reachable:', type(e).__name__, e)
"
