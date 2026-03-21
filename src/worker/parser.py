from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


class WorkerParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ParsedDocumentPayload:
    markdown: str
    canonical_json: dict


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
            stderr = completed.stderr.strip() or completed.stdout.strip() or "parser command failed"
            raise WorkerParseError(stderr)

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
