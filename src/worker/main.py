from src.config import get_settings
from src.database import SessionLocal
from src.queueing.dependencies import get_parse_job_queue
from src.storage.dependencies import get_object_storage
from src.worker.parser import DocumentAiCliParser
from src.worker.runner import WorkerRunner


def main() -> None:
    settings = get_settings()
    if not settings.document_ai_command:
        msg = "document_ai_command must be set to run the worker"
        raise RuntimeError(msg)

    runner = WorkerRunner(
        session_factory=SessionLocal,
        storage=get_object_storage(),
        queue=get_parse_job_queue(),
        parser=DocumentAiCliParser(
            command_template=settings.document_ai_command,
            timeout_seconds=settings.document_ai_timeout_seconds,
        ),
        temp_root=settings.worker_temp_root,
    )
    runner.run_forever(timeout_seconds=settings.worker_poll_timeout_seconds)


if __name__ == "__main__":
    main()
