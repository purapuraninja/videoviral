"""Discovery worker main loop: consume Redis jobs and run discovery.

Reads jobs from ``vvf:discovery`` (enqueued by the API on
POST /research-runs/{id}/start), runs the wigolo-backed pipeline, and marks the
research run completed/failed. Uses ``MockWigoloClient`` when no live wigolo is
reachable so dev works without the service.
"""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy.orm import Session

from vvf_database.models import ResearchRun
from vvf_database.session import build_engine, get_session_factory
from vvf_discovery_worker.pipeline import run_discovery
from vvf_shared.config import get_settings
from vvf_shared.logging import configure_logging, get_logger

DISCOVERY_QUEUE = "vvf:discovery"


def _make_wigolo_client():
    """Return a real WigoloClient, or MockWigoloClient if configured/unreachable."""
    use_mock = os.getenv("VVF_WIGOLO_USE_MOCK", "1") == "1"
    if use_mock:
        from vvf_wigolo import MockWigoloClient

        return MockWigoloClient()
    from vvf_wigolo import WigoloClient

    return WigoloClient()


def _get_redis():
    import redis

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _process(job: dict, session_factory) -> None:
    run_id = job.get("run_id")
    if not run_id:
        return
    log = get_logger()
    with session_factory() as db:  # type: Session
        run = db.get(ResearchRun, run_id)
        if run is None:
            log.warning(f"discovery: run {run_id} not found")
            return
        run.status = "running"
        db.commit()
        try:
            run_discovery(run, db, _make_wigolo_client())
        except Exception as exc:  # pragma: no cover - error path
            log.exception(f"discovery: run {run_id} failed: {exc}")
            run.status = "failed"
            db.commit()


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger()
    engine = build_engine(settings.database_dsn)
    session_factory = get_session_factory(engine)
    redis_client = _get_redis()
    log.info("discovery worker ready, waiting for jobs on 'vvf:discovery'")
    while True:
        try:
            item = redis_client.blpop(DISCOVERY_QUEUE, timeout=5)
        except Exception as exc:  # pragma: no cover
            log.warning(f"redis blpop error: {exc}; retrying in 5s")
            time.sleep(5)
            continue
        if item is None:
            continue
        _queue, value = item
        import json

        job = json.loads(value)
        log.info(f"discovery: picked up job {job}")
        _process(job, session_factory)


if __name__ == "__main__":
    sys.exit(main())
