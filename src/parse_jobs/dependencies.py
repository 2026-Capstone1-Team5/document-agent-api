from fastapi import Depends
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.parse_jobs.service import ParseJobService
from src.queueing.backends import ParseJobQueue
from src.queueing.dependencies import get_parse_job_queue
from src.storage.backends import ObjectStorage
from src.storage.dependencies import get_object_storage


def get_parse_job_service(
    session: Session = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
    queue: ParseJobQueue = Depends(get_parse_job_queue),
) -> ParseJobService:
    return ParseJobService(session=session, storage=storage, queue=queue)

