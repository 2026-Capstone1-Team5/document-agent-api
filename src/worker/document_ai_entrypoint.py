from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class EntrypointError(Exception):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_markdown_path(output_dir: Path, metadata: dict[str, Any]) -> Path:
    base_dir = output_dir.resolve()

    def _candidate_from_output(value: str) -> Path | None:
        raw = Path(value)
        candidate = raw.resolve() if raw.is_absolute() else (base_dir / raw).resolve()
        try:
            candidate.relative_to(base_dir)
        except ValueError:
            return None
        if candidate.exists():
            return candidate
        return None

    outputs = metadata.get("outputs")
    if isinstance(outputs, dict):
        selected_markdown = outputs.get("selected_markdown")
        if isinstance(selected_markdown, str):
            candidate = _candidate_from_output(selected_markdown)
            if candidate is not None:
                return candidate
        markdown = outputs.get("markdown")
        if isinstance(markdown, str):
            candidate = _candidate_from_output(markdown)
            if candidate is not None:
                return candidate

    candidates = [
        output_dir / "selected_markdown.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    msg = "document-ai output is missing markdown content"
    raise EntrypointError(msg)


def _build_canonical_json(
    *,
    metadata: dict[str, Any],
    input_path: Path,
    markdown_text: str,
) -> dict[str, Any]:
    canonical: dict[str, Any] = {
        "document": {
            "source": "document_ai",
            "filename": input_path.name,
            "parse_mode": metadata.get("parse_mode"),
            "language": metadata.get("language"),
        },
        "blocks": [
            {
                "type": "text",
                "text": markdown_text,
            }
        ],
        "engine": {
            "inspection": metadata.get("inspection"),
            "outputs": metadata.get("outputs"),
        },
    }
    return canonical


def run_entrypoint(
    *,
    input_path: Path,
    output_dir: Path,
    parse_script: Path,
    language: str,
    page_adaptive: bool,
    timeout_seconds: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    parse_script = parse_script.resolve()

    if not parse_script.exists():
        msg = f"parse script not found: {parse_script}"
        raise EntrypointError(msg)

    command = [
        sys.executable,
        str(parse_script),
        str(input_path),
        str(output_dir),
        "--language",
        language,
    ]
    if page_adaptive:
        command.append("--page-adaptive")

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "document-ai parse failed"
        raise EntrypointError(stderr)

    metadata_path = output_dir / "meta.json"
    if not metadata_path.exists():
        msg = "document-ai output is missing meta.json"
        raise EntrypointError(msg)

    metadata = _load_json(metadata_path)
    markdown_path = _resolve_markdown_path(output_dir, metadata)
    markdown_text = markdown_path.read_text(encoding="utf-8")

    canonical_json = _build_canonical_json(
        metadata=metadata,
        input_path=input_path,
        markdown_text=markdown_text,
    )

    (output_dir / "result.md").write_text(markdown_text, encoding="utf-8")
    (output_dir / "result.json").write_text(
        json.dumps(canonical_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run document-ai parser and normalize outputs for document-agent-api worker.",
    )
    parser.add_argument("input_path")
    parser.add_argument("output_dir")
    parser.add_argument(
        "--parse-script",
        default="vendor/document-ai/scripts/parse_document.py",
    )
    parser.add_argument("--language", default="ko")
    parser.add_argument("--page-adaptive", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        run_entrypoint(
            input_path=Path(args.input_path).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            parse_script=Path(args.parse_script),
            language=args.language,
            page_adaptive=bool(args.page_adaptive),
            timeout_seconds=args.timeout_seconds,
        )
    except (EntrypointError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
