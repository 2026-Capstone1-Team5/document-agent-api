from uuid import UUID


class ParseJobNotFoundError(Exception):
    def __init__(self, job_id: UUID) -> None:
        super().__init__(f"Parse job '{job_id}' was not found.")
        self.job_id = job_id


class ParseJobEnqueueError(Exception):
    def __init__(self, job_id: UUID) -> None:
        super().__init__(f"Parse job '{job_id}' could not be enqueued.")
        self.job_id = job_id

