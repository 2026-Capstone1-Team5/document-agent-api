from src.config import get_settings
from src.database import SessionLocal
from src.model_registry import load_model_registry
from src.parser_backends import ParserBackend
from src.queueing.dependencies import get_parse_job_queue
from src.storage.dependencies import get_object_storage
from src.worker.parser import (
    DocumentAIParser,
    MarkItDownParser,
    PdftotextParser,
    WorkerParser,
)
from src.worker.runner import WorkerRunner


def _build_parsers() -> dict[ParserBackend, WorkerParser]:
    settings = get_settings()
    parsers: dict[ParserBackend, WorkerParser] = {
        "markitdown": MarkItDownParser(),
        "pdftotext": PdftotextParser(
            command=settings.pdftotext_command,
            timeout_seconds=settings.parser_timeout_seconds,
        ),
    }
    if "document_ai" in settings.enabled_parser_backends:
        if not settings.document_ai_script_path:
            msg = "document_ai_script_path is required when document_ai backend is enabled"
            raise RuntimeError(msg)
        parsers["document_ai"] = DocumentAIParser(
            script_path=settings.document_ai_script_path,
            timeout_seconds=settings.parser_timeout_seconds,
        )
    return parsers


def main() -> None:
    settings = get_settings()
    load_model_registry()
    runner = WorkerRunner(
        session_factory=SessionLocal,
        storage=get_object_storage(),
        queue=get_parse_job_queue(),
        parsers=_build_parsers(),
        temp_root=settings.worker_temp_root,
    )
    runner.run_forever(timeout_seconds=settings.worker_poll_timeout_seconds)


if __name__ == "__main__":
    main()
