from functools import lru_cache

from src.config import get_settings
from src.storage.backends import LocalObjectStorage, ObjectStorage, R2ObjectStorage


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    if settings.storage_backend == "r2":
        return R2ObjectStorage(
            bucket=settings.storage_bucket or "",
            endpoint=settings.storage_r2_endpoint or "",
            access_key_id=settings.storage_r2_access_key_id or "",
            secret_access_key=settings.storage_r2_secret_access_key or "",
            region=settings.storage_r2_region,
        )

    return LocalObjectStorage(root=settings.storage_local_root)
