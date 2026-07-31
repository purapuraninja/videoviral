\echo '=== render_jobs ==='
select id, status, candidate_id, claimed_by_agent_id, attempt, left(coalesce(error_message,''),60) as err, created_at from render_jobs order by created_at desc limit 5;
\echo '=== candidates ==='
select id, status, left(title,50) as title from content_candidates order by created_at desc limit 5;
\echo '=== agents ==='
select id, name, last_heartbeat_at from agents;
