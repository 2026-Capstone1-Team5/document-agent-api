from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from src.auth.models import UserModel
from src.auth.security import hash_password
from src.documents.models import DocumentModel
from src.parse_jobs.models import ParseJobModel
from src.parse_jobs.service import ParseJobService
from src.queueing.backends import InMemoryParseJobQueue
from src.worker.parser import ParsedDocumentPayload, WorkerParseError
from src.worker.runner import WorkerRunner


def _create_user(session, *, email: str = "owner@example.com") -> str:
    user = UserModel(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password("password123!"),
    )
    session.add(user)
    session.commit()
    return user.id


class SuccessfulParser:
    def parse(self, *, input_path, output_dir):  # type: ignore[no-untyped-def]
        del input_path, output_dir
        return ParsedDocumentPayload(
            markdown="# parsed",
            canonical_json={"document": {"title": "parsed"}},
        )


class FailingParser:
    def parse(self, *, input_path, output_dir):  # type: ignore[no-untyped-def]
        del input_path, output_dir
        raise WorkerParseError("parser failed")


def test_worker_runner_creates_document_and_marks_job_succeeded(
    tmp_path,
    db_session,
    object_storage,
) -> None:
    queue = InMemoryParseJobQueue()
    owner_user_id = _create_user(db_session)
    job_service = ParseJobService(session=db_session, storage=object_storage, queue=queue)
    created = job_service.create_job(
        owner_user_id=owner_user_id,
        filename="demo.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-demo",
    )

    runner = WorkerRunner(
        session_factory=sessionmaker(
            bind=db_session.bind,
            autocommit=False,
            autoflush=False,
        ),
        storage=object_storage,
        queue=queue,
        parser=SuccessfulParser(),  # type: ignore[arg-type]
        temp_root=str(tmp_path),
    )

    processed = runner.run_once(timeout_seconds=1)

    assert processed is True
    refreshed_job = db_session.get(ParseJobModel, str(created.job.id))
    assert refreshed_job is not None
    assert refreshed_job.status == "succeeded"
    assert refreshed_job.document_id is not None
    document = db_session.get(DocumentModel, refreshed_job.document_id)
    assert document is not None


def test_worker_runner_marks_job_failed_on_parser_error(
    tmp_path,
    db_session,
    object_storage,
) -> None:
    queue = InMemoryParseJobQueue()
    owner_user_id = _create_user(db_session, email="parser@example.com")
    job_service = ParseJobService(session=db_session, storage=object_storage, queue=queue)
    created = job_service.create_job(
        owner_user_id=owner_user_id,
        filename="demo.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-demo",
    )

    runner = WorkerRunner(
        session_factory=sessionmaker(
            bind=db_session.bind,
            autocommit=False,
            autoflush=False,
        ),
        storage=object_storage,
        queue=queue,
        parser=FailingParser(),  # type: ignore[arg-type]
        temp_root=str(tmp_path),
    )

    processed = runner.run_once(timeout_seconds=1)

    assert processed is True
    refreshed_job = db_session.get(ParseJobModel, str(created.job.id))
    assert refreshed_job is not None
    assert refreshed_job.status == "failed"
    assert refreshed_job.error_code == "parse_failed"


def test_worker_runner_skips_payload_without_job_id(
    tmp_path,
    db_session,
    object_storage,
) -> None:
    queue = InMemoryParseJobQueue()
    queue.enqueue_parse_job(payload={"filename": "demo.pdf"})

    runner = WorkerRunner(
        session_factory=sessionmaker(
            bind=db_session.bind,
            autocommit=False,
            autoflush=False,
        ),
        storage=object_storage,
        queue=queue,
        parser=SuccessfulParser(),  # type: ignore[arg-type]
        temp_root=str(tmp_path),
    )

    processed = runner.run_once(timeout_seconds=1)

    assert processed is True


def test_worker_runner_skips_payload_with_invalid_job_id(
    tmp_path,
    db_session,
    object_storage,
) -> None:
    queue = InMemoryParseJobQueue()
    queue.enqueue_parse_job(payload={"job_id": "not-a-uuid"})

    runner = WorkerRunner(
        session_factory=sessionmaker(
            bind=db_session.bind,
            autocommit=False,
            autoflush=False,
        ),
        storage=object_storage,
        queue=queue,
        parser=SuccessfulParser(),  # type: ignore[arg-type]
        temp_root=str(tmp_path),
    )

    processed = runner.run_once(timeout_seconds=1)

    assert processed is True
