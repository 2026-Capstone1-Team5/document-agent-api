from src.config import get_settings
from src.database import SessionLocal
from src.model_registry import load_model_registry
from src.queueing.dependencies import get_parse_job_queue
from src.storage.dependencies import get_object_storage
from src.worker.parser import MarkItDownParser, PdftotextParser
from src.worker.runner import WorkerRunner


def _build_parser():
    settings = get_settings()
    if settings.parser_backend == "markitdown":
        return MarkItDownParser(timeout_seconds=settings.parser_timeout_seconds)

    return PdftotextParser(
        command=settings.pdftotext_command,
        timeout_seconds=settings.parser_timeout_seconds,
    )


def main() -> None:
    settings = get_settings()
    load_model_registry()
    runner = WorkerRunner(
        session_factory=SessionLocal,
        storage=get_object_storage(),
        queue=get_parse_job_queue(),
        parser=_build_parser(),
        temp_root=settings.worker_temp_root,
    )
    runner.run_forever(timeout_seconds=settings.worker_poll_timeout_seconds)


if __name__ == "__main__":
    main()
