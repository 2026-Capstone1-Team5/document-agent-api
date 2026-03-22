from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class WorkerParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ParsedDocumentPayload:
    markdown: str
    canonical_json: dict


class WorkerParser(Protocol):
    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload: ...


class MarkItDownParser:
    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload:
        del output_dir
        try:
            from markitdown import MarkItDown
        except ImportError as exc:
            msg = "markitdown is not installed"
            raise WorkerParseError(msg) from exc

        converter = MarkItDown(enable_plugins=False)
        try:
            result = converter.convert(str(input_path))
        except Exception as exc:  # noqa: BLE001
            raise WorkerParseError(str(exc)) from exc

        text = result.text_content.strip()
        if not text:
            msg = "markitdown returned no extractable text"
            raise WorkerParseError(msg)

        canonical_json = {
            "document": {
                "source": "markitdown",
                "filename": input_path.name,
            },
            "blocks": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        return ParsedDocumentPayload(markdown=text, canonical_json=canonical_json)


class PdftotextParser:
    def __init__(self, *, command: str, timeout_seconds: int) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload:
        del output_dir
        completed = subprocess.run(
            [self.command, "-layout", str(input_path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "pdftotext failed"
            raise WorkerParseError(stderr)

        text = completed.stdout.strip()
        if not text:
            msg = "pdftotext returned no extractable text"
            raise WorkerParseError(msg)

        markdown = text
        canonical_json = {
            "document": {
                "source": "pdftotext",
                "filename": input_path.name,
            },
            "blocks": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
        return ParsedDocumentPayload(markdown=markdown, canonical_json=canonical_json)
