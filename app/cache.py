import json
import logging
import os

import redis

log = logging.getLogger("uvicorn.error")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TTL_SECONDS = 600  # cached results expire after 10 minutes

client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_json(key: str):
    """Return the cached value for key, or None on a miss or if Redis is down."""
    try:
        raw = client.get(key)
    except redis.RedisError as e:
        log.warning("Redis unavailable, skipping cache: %s", e)
        return None
    return json.loads(raw) if raw else None


def set_json(key: str, value: dict, ttl: int = TTL_SECONDS) -> None:
    """Store value under key for ttl seconds."""
    try:
        client.set(key, json.dumps(value), ex=ttl)
    except redis.RedisError as e:
        log.warning("Redis unavailable, not caching: %s", e)


def clear_risk_cache() -> int:
    """Delete every cached risk result. Returns how many were removed."""
    try:
        keys = list(client.scan_iter("risk:*"))
        return client.delete(*keys) if keys else 0
    except redis.RedisError as e:
        log.warning("Redis unavailable, could not clear cache: %s", e)
        return 0