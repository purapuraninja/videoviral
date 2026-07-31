"""Redis-backed job queue for discovery + render orchestration.

The API enqueues discovery jobs; the discovery-worker consumes them and writes
results to PostgreSQL. Render jobs are pulled by local render agents via the
claim endpoint rather than pushed through Redis (agents poll outward).
"""

from __future__ import annotations

import json
from typing import Any

import redis

from vvf_shared.config import get_settings

_client: redis.Redis | None = None

DISCOVERY_QUEUE = "vvf:discovery"


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def enqueue_discovery(run_id: str, payload: dict[str, Any] | None = None) -> None:
    get_redis().rpush(
        DISCOVERY_QUEUE,
        json.dumps({"run_id": run_id, "payload": payload or {}}),
    )


def dequeue_discovery(timeout: int = 5) -> dict[str, Any] | None:
    item = get_redis().blpop(DISCOVERY_QUEUE, timeout=timeout)
    if item is None:
        return None
    _queue, value = item
    return json.loads(value)
