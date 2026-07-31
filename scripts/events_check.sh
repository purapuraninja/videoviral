#!/usr/bin/env bash
# Show recent render job events (optionally for one job id).
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
PSQL="docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c"
JOB="${1:-}"

if [ -n "$JOB" ]; then
  echo "=== events for $JOB ==="
  $PSQL "select concat(created_at::text,' | ',status,' | ',progress,'% | ',message,' | log=',coalesce(left(log,200),'-')) from render_job_events where job_id='$JOB' order by created_at;"
  echo "=== job row ==="
  $PSQL "select concat(status,' | attempt=',attempt,' | agent=',coalesce(claimed_by_agent_id,'-'),' | err=',coalesce(error_message,'-')) from render_jobs where id='$JOB';"
else
  echo "=== latest 12 events (all jobs) ==="
  $PSQL "select concat(created_at::text,' | ',job_id,' | ',status,' | ',progress,'% | ',message,' | log=',coalesce(left(log,150),'-')) from render_job_events order by created_at desc limit 12;"
fi
