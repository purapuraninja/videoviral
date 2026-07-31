#!/usr/bin/env bash
# Show publish targets (optionally for one job id).
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
JOB="${1:-}"
WHERE=""
[ -n "$JOB" ] && WHERE="where job_id = '$JOB'"

docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select concat(platform, ' | ', mode, ' | ', status, ' | attempt=', attempt,
                 ' | url=', coalesce(post_url, '-'),
                 ' | err=', coalesce(left(error_message, 120), '-'))
   from publish_targets $WHERE order by platform;"

echo "--- job status ---"
docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c \
  "select concat(id, ' | ', status) from render_jobs
   where id in (select distinct job_id from publish_targets $WHERE) order by created_at desc;"
