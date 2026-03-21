from src.config import get_settings
from src.queueing.backends import (
    InMemoryParseJobQueue,
    LoggingParseJobQueue,
    ParseJobQueue,
    RedisParseJobQueue,
)


def get_parse_job_queue() -> ParseJobQueue:
    settings = get_settings()
    if settings.queue_backend == "redis":
        return RedisParseJobQueue(
            redis_url=settings.redis_url,
            queue_name=settings.parse_job_queue_name,
        )
    if settings.queue_backend == "memory":
        return InMemoryParseJobQueue()
    return LoggingParseJobQueue()

