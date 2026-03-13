from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] | None = field(default=None)
