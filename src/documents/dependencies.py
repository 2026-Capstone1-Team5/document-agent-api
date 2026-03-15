from fastapi import Depends
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.documents.service import DocumentService
from src.storage.backends import ObjectStorage
from src.storage.dependencies import get_object_storage


def get_document_service(
    session: Session = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> DocumentService:
    return DocumentService(session=session, storage=storage)
