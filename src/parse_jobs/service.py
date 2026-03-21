from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.documents.utils import sanitize_document_filename
from src.parse_jobs.exceptions import ParseJobEnqueueError, ParseJobNotFoundError
from src.parse_jobs.models import ParseJobModel
from src.parse_jobs.schemas import ParseJobResponse, ParseJobSummary
from src.queueing.backends import ParseJobQueue
from src.storage.backends import ObjectStorage

logger = logging.getLogger(__name__)


class ParseJobService:
    def __init__(
        self,
        *,
        session: Session,
        storage: ObjectStorage,
        queue: ParseJobQueue,
    ) -> None:
        self.session = session
        self.storage = storage
        self.queue = queue

    def create_job(
        self,
        *,
        owner_user_id: str,
        filename: str,
        content_type: str,
        file_data: bytes,
    ) -> ParseJobResponse:
        job_id = str(uuid4())
        safe_filename = sanitize_document_filename(filename)
        source_object_key = f"parse-jobs/{job_id}/source/{safe_filename}"
        job_persisted = False

        try:
            self.storage.put_bytes(
                key=source_object_key,
                data=file_data,
                content_type=content_type,
            )

            job = ParseJobModel(
                id=job_id,
                owner_user_id=owner_user_id,
                source_object_key=source_object_key,
                filename=filename,
                content_type=content_type,
                status="queued",
            )
            self.session.add(job)
            self.session.commit()
            job_persisted = True
            self.queue.enqueue_parse_job(
                payload={
                    "job_id": job_id,
                    "owner_user_id": owner_user_id,
                    "source_object_key": source_object_key,
                    "filename": filename,
                    "content_type": content_type,
                }
            )
        except Exception as exc:
            self.session.rollback()
            if not job_persisted:
                self._cleanup_source_object_best_effort(
                    job_id=job_id,
                    source_object_key=source_object_key,
                )
            else:
                self._mark_enqueue_failure(job_id=job_id)
            logger.exception("failed to enqueue parse job id=%s", job_id)
            raise ParseJobEnqueueError(UUID(job_id)) from exc

        self.session.refresh(job)
        return ParseJobResponse(job=self._to_summary(job))

    def get_job(self, job_id: UUID, *, owner_user_id: str) -> ParseJobResponse:
        statement = select(ParseJobModel).where(
            ParseJobModel.id == str(job_id),
            ParseJobModel.owner_user_id == owner_user_id,
        )
        job = self.session.scalars(statement).first()
        if job is None:
            raise ParseJobNotFoundError(job_id)
        return ParseJobResponse(job=self._to_summary(job))

    def _mark_enqueue_failure(self, *, job_id: str) -> None:
        job = self.session.get(ParseJobModel, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error_code = "queue_enqueue_failed"
        job.error_message = "The parse job could not be added to the queue."
        self.session.add(job)
        self.session.commit()

    def _cleanup_source_object_best_effort(self, *, job_id: str, source_object_key: str) -> None:
        try:
            self.storage.delete_object(key=source_object_key)
        except Exception:
            logger.warning(
                "failed to delete source object for parse job id=%s key=%s",
                job_id,
                source_object_key,
                exc_info=True,
            )

    @staticmethod
    def _to_summary(job: ParseJobModel) -> ParseJobSummary:
        return ParseJobSummary(
            id=UUID(job.id),
            filename=job.filename,
            contentType=job.content_type,
            status=job.status,
            documentId=UUID(job.document_id) if job.document_id else None,
            errorCode=job.error_code,
            errorMessage=job.error_message,
            createdAt=job.created_at,
            updatedAt=job.updated_at,
            startedAt=job.started_at,
            finishedAt=job.finished_at,
        )
