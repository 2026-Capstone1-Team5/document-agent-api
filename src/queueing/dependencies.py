from functools import lru_cache

from src.config import get_settings
from src.queueing.backends import (
    InMemoryParseJobQueue,
    LoggingParseJobQueue,
    ParseJobQueue,
    RedisParseJobQueue,
)


@lru_cache(maxsize=1)
def _get_memory_queue() -> InMemoryParseJobQueue:
    return InMemoryParseJobQueue()


@lru_cache(maxsize=1)
def _get_logging_queue() -> LoggingParseJobQueue:
    return LoggingParseJobQueue()


@lru_cache(maxsize=8)
def _get_redis_queue(redis_url: str, queue_name: str) -> RedisParseJobQueue:
    return RedisParseJobQueue(redis_url=redis_url, queue_name=queue_name)


def get_parse_job_queue() -> ParseJobQueue:
    settings = get_settings()
    if settings.queue_backend == "redis":
        return _get_redis_queue(
            redis_url=settings.redis_url,
            queue_name=settings.parse_job_queue_name,
        )
    if settings.queue_backend == "memory":
        return _get_memory_queue()
    return _get_logging_queue()
