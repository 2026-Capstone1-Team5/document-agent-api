from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from src.documents.service import DocumentService
from src.parse_jobs.service import ParseJobService
from src.queueing.backends import ParseJobQueue
from src.storage.backends import ObjectStorage
from src.worker.parser import WorkerParseError, WorkerParser

logger = logging.getLogger(__name__)


class WorkerRunner:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        queue: ParseJobQueue,
        parser: WorkerParser,
        temp_root: str,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.queue = queue
        self.parser = parser
        self.temp_root = Path(temp_root)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def run_once(self, *, timeout_seconds: int) -> bool:
        payload = self.queue.dequeue_parse_job(timeout_seconds=timeout_seconds)
        if payload is None:
            return False

        try:
            raw_job_id = payload["job_id"]
        except KeyError:
            logger.error("received parse job payload without job_id: %r", payload)
            return True

        try:
            job_id = UUID(str(raw_job_id))
        except (TypeError, ValueError) as exc:
            logger.error("received parse job payload with invalid job_id %r: %s", raw_job_id, exc)
            return True

        with self.session_factory() as session:
            job_service = ParseJobService(session=session, storage=self.storage, queue=self.queue)
            job = job_service.start_job(job_id)

        if job is None:
            logger.info("skipping parse job id=%s because it is not queued anymore", job_id)
            return True

        try:
            source_data = self.storage.get_bytes(key=job.source_object_key)
            with tempfile.TemporaryDirectory(dir=self.temp_root) as temp_dir:
                working_dir = Path(temp_dir)
                input_path = working_dir / Path(job.filename).name
                input_path.write_bytes(source_data)
                parsed = self.parser.parse(input_path=input_path, output_dir=working_dir)

            with self.session_factory() as session:
                document_service = DocumentService(session=session, storage=self.storage)
                job_service = ParseJobService(
                    session=session,
                    storage=self.storage,
                    queue=self.queue,
                )
                created = document_service.create_document_from_parse_result(
                    owner_user_id=job.owner_user_id,
                    source_object_key=job.source_object_key,
                    filename=job.filename,
                    content_type=job.content_type,
                    markdown_content=parsed.markdown,
                    canonical_json_content=parsed.canonical_json,
                )
                job_service.complete_job(
                    job_id=job.id,
                    document_id=created.document.id,
                )
        except WorkerParseError as exc:
            self._fail_job(job_id=job.id, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker failed while processing parse job id=%s", job.id)
            self._fail_job(job_id=job.id, error_message=str(exc))

        return True

    def run_forever(self, *, timeout_seconds: int) -> None:
        while True:
            self.run_once(timeout_seconds=timeout_seconds)

    def _fail_job(self, *, job_id: UUID, error_message: str) -> None:
        with self.session_factory() as session:
            job_service = ParseJobService(session=session, storage=self.storage, queue=self.queue)
            job_service.fail_job(
                job_id=job_id,
                error_code="parse_failed",
                error_message=error_message,
            )
