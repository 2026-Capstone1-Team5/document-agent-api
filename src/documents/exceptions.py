from uuid import UUID


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"Document not found: {document_id}")
