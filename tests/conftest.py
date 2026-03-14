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

from src.database import Base
from src.documents import models  # noqa: F401


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
