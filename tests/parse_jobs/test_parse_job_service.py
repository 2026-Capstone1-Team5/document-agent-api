from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import UserModel
from src.auth.security import hash_password
from src.parse_jobs.exceptions import ParseJobEnqueueError, ParseJobNotFoundError
from src.parse_jobs.models import ParseJobModel
from src.parse_jobs.service import ParseJobService
from src.queueing.backends import InMemoryParseJobQueue
from src.storage.backends import LocalObjectStorage


def _create_user(db_session, *, email: str = "owner@example.com") -> str:
    user = UserModel(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password("password123!"),
    )
    db_session.add(user)
    db_session.commit()
    return user.id


def test_create_job_persists_job_and_enqueues_message(db_session, object_storage) -> None:
    queue = InMemoryParseJobQueue()
    service = ParseJobService(session=db_session, storage=object_storage, queue=queue)
    owner_user_id = _create_user(db_session)

    created = service.create_job(
        owner_user_id=owner_user_id,
        filename="demo.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-demo",
    )

    assert created.job.status == "queued"
    assert created.job.filename == "demo.pdf"
    stored = db_session.get(ParseJobModel, str(created.job.id))
    assert stored is not None
    assert stored.source_object_key is not None
    assert queue.messages[0]["job_id"] == str(created.job.id)


def test_get_job_raises_for_other_user(db_session, object_storage) -> None:
    queue = InMemoryParseJobQueue()
    service = ParseJobService(session=db_session, storage=object_storage, queue=queue)
    owner_user_id = _create_user(db_session, email="owner@example.com")
    other_user_id = _create_user(db_session, email="other@example.com")
    created = service.create_job(
        owner_user_id=owner_user_id,
        filename="demo.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-demo",
    )

    with pytest.raises(ParseJobNotFoundError):
        service.get_job(UUID(str(created.job.id)), owner_user_id=other_user_id)


def test_create_job_marks_failure_when_enqueue_fails(db_session, object_storage) -> None:
    class FailingQueue:
        def enqueue_parse_job(self, *, payload):  # type: ignore[no-untyped-def]
            del payload
            raise RuntimeError("queue unavailable")

    service = ParseJobService(session=db_session, storage=object_storage, queue=FailingQueue())
    owner_user_id = _create_user(db_session)

    with pytest.raises(ParseJobEnqueueError):
        service.create_job(
            owner_user_id=owner_user_id,
            filename="demo.pdf",
            content_type="application/pdf",
            file_data=b"%PDF-demo",
        )

    stored = db_session.scalars(select(ParseJobModel)).first()
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error_code == "queue_enqueue_failed"


def test_create_job_with_dotdot_filename_uses_safe_key(db_session, tmp_path) -> None:
    storage = LocalObjectStorage(root=str(tmp_path))
    queue = InMemoryParseJobQueue()
    service = ParseJobService(session=db_session, storage=storage, queue=queue)
    owner_user_id = _create_user(db_session)

    created = service.create_job(
        owner_user_id=owner_user_id,
        filename="..",
        content_type="application/pdf",
        file_data=b"%PDF-demo",
    )

    stored = db_session.get(ParseJobModel, str(created.job.id))
    assert stored is not None
    assert stored.source_object_key is not None
    assert stored.source_object_key.endswith("/uploaded.bin")


def test_create_job_cleans_up_source_object_when_commit_fails(db_session, tmp_path) -> None:
    class CommitFailingSession:
        def __init__(self, wrapped: Session) -> None:
            self._wrapped = wrapped

        def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
            return getattr(self._wrapped, name)

        def commit(self) -> None:
            raise RuntimeError("forced commit failure")

    storage = LocalObjectStorage(root=str(tmp_path))
    queue = InMemoryParseJobQueue()
    normal_session = db_session
    failing_session = CommitFailingSession(normal_session)
    service = ParseJobService(session=failing_session, storage=storage, queue=queue)
    owner_user_id = _create_user(normal_session)

    with pytest.raises(ParseJobEnqueueError):
        service.create_job(
            owner_user_id=owner_user_id,
            filename="../demo.pdf",
            content_type="application/pdf",
            file_data=b"%PDF-demo",
        )

    assert list(tmp_path.rglob("*.pdf")) == []
    assert normal_session.scalars(select(ParseJobModel)).first() is None
    assert normal_session.scalars(select(ParseJobModel)).first() is None
