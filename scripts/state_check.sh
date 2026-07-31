#!/usr/bin/env bash
# Show current pipeline state: candidates, jobs, outputs, agents.
set -uo pipefail
cd /opt/viral-video-factory/repo/vvf
PSQL="docker compose -f docker-compose.prod.yml exec -T postgres psql -U vvf -d vvf -tA -c"

echo "=== agents ==="
$PSQL "select concat(name,' | preview=',coalesce(nullif(preview_base_url,''),'(none)'),' | hb=',coalesce(last_heartbeat_at::text,'never'),' | active=',coalesce(active_job_id,'-')) from agents order by name;"

echo "=== research runs (latest 5) ==="
$PSQL "select concat(id,' | ',status,' | ',keyword) from research_runs order by created_at desc limit 5;"

echo "=== candidates (latest 8) ==="
$PSQL "select concat(id,' | ',status,' | rank=',coalesce(rank::text,'-'),' | ',left(title,45)) from content_candidates order by created_at desc limit 8;"

echo "=== render jobs (latest 8) ==="
$PSQL "select concat(id,' | ',status,' | attempt=',attempt,' | ',created_at::text) from render_jobs order by created_at desc limit 8;"

echo "=== video outputs (latest 8) ==="
$PSQL "select concat(job_id,' | ',artifact_type,' | agent=',coalesce(agent_id,'-'),' | local=',coalesce(left(local_path,50),'-')) from video_outputs order by created_at desc limit 8;"

echo "=== render profiles ==="
$PSQL "select concat(name,' | ',resolution,' | ',duration_seconds::text,'s | ',language) from render_profiles order by name;"
