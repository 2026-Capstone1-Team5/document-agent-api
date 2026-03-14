from fastapi import Depends
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.documents.service import DocumentService


def get_document_service(
    session: Session = Depends(get_db_session),
) -> DocumentService:
    return DocumentService(session=session)
