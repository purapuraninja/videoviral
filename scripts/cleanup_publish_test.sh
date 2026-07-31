#!/usr/bin/env bash
# Remove publish targets created by verification runs and restore the job status.
# Usage: bash scripts/cleanup_publish_test.sh <job_id>
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
JOB="${1:?usage: cleanup_publish_test.sh <job_id>}"
PSQL="docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c"

echo "=== deleting publish targets for $JOB ==="
$PSQL "delete from publish_targets where job_id = '$JOB';"

echo "=== deleting publish events for $JOB ==="
$PSQL "delete from render_job_events where job_id = '$JOB' and status in ('publishing','published');"

echo "=== restoring job status to completed ==="
$PSQL "update render_jobs set status = 'completed' where id = '$JOB' and status in ('publishing','published','publish_failed');"

echo "=== state ==="
$PSQL "select concat(id, ' | ', status) from render_jobs where id = '$JOB';"
$PSQL "select count(*) || ' publish targets remain' from publish_targets where job_id = '$JOB';"
