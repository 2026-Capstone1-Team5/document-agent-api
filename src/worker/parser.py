from __future__ import annotations

import json
import shlex
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


class DocumentAiCliParser:
    def __init__(self, *, command_template: str, timeout_seconds: int) -> None:
        self.command_template = command_template
        self.timeout_seconds = timeout_seconds

    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload:
        command = self._build_command(input_path=input_path, output_dir=output_dir)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise WorkerParseError(self._format_subprocess_failure(completed))

        markdown_path = self._find_markdown_path(output_dir)
        json_path = self._find_json_path(output_dir)
        if markdown_path is None or json_path is None:
            msg = "parser output is missing required result.md or result.json files"
            raise WorkerParseError(msg)

        return ParsedDocumentPayload(
            markdown=markdown_path.read_text(encoding="utf-8"),
            canonical_json=json.loads(json_path.read_text(encoding="utf-8")),
        )

    def _build_command(self, *, input_path: Path, output_dir: Path) -> list[str]:
        rendered = self.command_template.format(
            input_path=str(input_path),
            output_dir=str(output_dir),
        )
        return shlex.split(rendered)

    @staticmethod
    def _find_markdown_path(output_dir: Path) -> Path | None:
        candidates = [
            output_dir / "result.md",
            output_dir / "selected_markdown.md",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _find_json_path(output_dir: Path) -> Path | None:
        candidates = [
            output_dir / "result.json",
            output_dir / "canonical.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _format_subprocess_failure(completed: subprocess.CompletedProcess[str]) -> str:
        exit_code = completed.returncode
        signal_part = f", signal={-exit_code}" if exit_code < 0 else ""
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout
        if detail:
            trimmed = detail[-1200:]
            return (
                f"parser command failed (exit_code={exit_code}{signal_part}): {trimmed}"
            )
        return f"parser command failed (exit_code={exit_code}{signal_part})"


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
