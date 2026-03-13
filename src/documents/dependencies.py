from src.documents.service import DocumentService

# TODO: Replace the in-memory service state with SQLAlchemy-backed persistence
# once `models.py`, sessions, and migrations are introduced.
_document_service = DocumentService.seeded()


def get_document_service() -> DocumentService:
    return _document_service
