# ruff: noqa: E402

import sys
from os import getenv
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auth import models as auth_models  # noqa: F401
from src.database import Base
from src.documents import models  # noqa: F401


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        del content_type
        self._objects[key] = data
        return key

    def get_bytes(self, *, key: str) -> bytes:
        return self._objects[key]

    def delete_object(self, *, key: str) -> None:
        self._objects.pop(key, None)


@pytest.fixture
def db_engine():
    database_url = getenv("DOCUMENT_AGENT_API_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set DOCUMENT_AGENT_API_TEST_DATABASE_URL to run PostgreSQL-backed tests.",
        )
    engine = create_engine(database_url)
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def object_storage() -> InMemoryObjectStorage:
    return InMemoryObjectStorage()
