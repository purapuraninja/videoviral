\echo '=== job ==='
select status, claimed_by_agent_id, attempt from render_jobs where id='rj_86c1cba9f0964e2ca7622cfb';
\echo '=== recent events ==='
select created_at::time(0), status, message, progress from render_job_events where job_id='rj_86c1cba9f0964e2ca7622cfb' order by created_at desc limit 6;
\echo '=== outputs ==='
select artifact_type, left(storage_url,60) from video_outputs where job_id='rj_86c1cba9f0964e2ca7622cfb';
