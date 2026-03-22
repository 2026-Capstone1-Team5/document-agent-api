from typing import Literal, get_args

ParserBackend = Literal["markitdown", "pdftotext"]

DEFAULT_REQUEST_PARSER_BACKEND: ParserBackend = "markitdown"
PARSER_BACKEND_VALUES = set(get_args(ParserBackend))


def normalize_parser_backend(value: str) -> ParserBackend:
    normalized = value.strip().lower()
    if normalized not in PARSER_BACKEND_VALUES:
        msg = "parser backend must be one of: pdftotext, markitdown"
        raise ValueError(msg)
    return normalized  # type: ignore[return-value]
