from typing import Literal, get_args

ParserBackend = Literal["markitdown", "pdftotext", "document_ai"]

DEFAULT_REQUEST_PARSER_BACKEND: ParserBackend = "markitdown"
PARSER_BACKEND_VALUES = get_args(ParserBackend)
DEFAULT_ENABLED_PARSER_BACKENDS: tuple[ParserBackend, ...] = (
    "markitdown",
    "pdftotext",
)
PARSER_BACKEND_VALUES_SET = set(PARSER_BACKEND_VALUES)


def normalize_parser_backend(value: str) -> ParserBackend:
    normalized = value.strip().lower()
    if normalized not in PARSER_BACKEND_VALUES_SET:
        msg = f"parser backend must be one of: {', '.join(PARSER_BACKEND_VALUES)}"
        raise ValueError(msg)
    return normalized  # type: ignore[return-value]
