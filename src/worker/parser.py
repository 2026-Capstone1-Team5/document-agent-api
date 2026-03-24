from __future__ import annotations

import json
import subprocess
import sys
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


class DocumentAIParser:
    def __init__(self, *, script_path: str, timeout_seconds: int) -> None:
        self.script_path = Path(script_path)
        self.timeout_seconds = timeout_seconds

    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload:
        if not self.script_path.is_file():
            msg = f"document-ai script is not available: {self.script_path}"
            raise WorkerParseError(msg)

        document_ai_output_dir = output_dir / "document_ai_output"
        document_ai_output_dir.mkdir(parents=True, exist_ok=True)

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(self.script_path),
                    str(input_path),
                    str(document_ai_output_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkerParseError("document-ai parsing timed out") from exc

        if completed.returncode != 0:
            stderr = (
                completed.stderr.strip() or completed.stdout.strip() or "document-ai parsing failed"
            )
            raise WorkerParseError(stderr)

        metadata_path = document_ai_output_dir / "meta.json"
        if not metadata_path.is_file():
            msg = "document-ai did not produce meta.json"
            raise WorkerParseError(msg)

        try:
            metadata = json.loads(metadata_path.read_text())
        except json.JSONDecodeError as exc:
            raise WorkerParseError("document-ai produced invalid meta.json") from exc

        outputs = metadata.get("outputs")
        if not isinstance(outputs, dict):
            msg = "document-ai meta.json is missing outputs"
            raise WorkerParseError(msg)

        markdown_output = outputs.get("selected_markdown") or outputs.get("markdown")
        if not isinstance(markdown_output, str) or not markdown_output.strip():
            msg = "document-ai meta.json is missing a markdown output"
            raise WorkerParseError(msg)

        markdown_path = Path(markdown_output)
        if not markdown_path.is_absolute():
            markdown_path = (document_ai_output_dir / markdown_path).resolve()
        if not markdown_path.is_file():
            msg = f"document-ai markdown output not found: {markdown_path}"
            raise WorkerParseError(msg)

        markdown = markdown_path.read_text(errors="ignore").strip()
        if not markdown:
            msg = "document-ai returned no extractable text"
            raise WorkerParseError(msg)

        canonical_json = {
            "document": {
                "source": "document_ai",
                "filename": input_path.name,
                "parse_mode": metadata.get("parse_mode"),
            },
            "blocks": [
                {
                    "type": "text",
                    "text": markdown,
                }
            ],
        }
        return ParsedDocumentPayload(markdown=markdown, canonical_json=canonical_json)
