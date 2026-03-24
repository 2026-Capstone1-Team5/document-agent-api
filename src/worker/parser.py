from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class WorkerParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ParsedDocumentPayload:
    markdown: str
    canonical_json: dict


class WorkerParser(Protocol):
    def parse(self, *, input_path: Path, output_dir: Path) -> ParsedDocumentPayload: ...


def _read_json_file(path: Path) -> object | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _normalize_bbox(raw_bbox: object) -> list[float] | None:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None

    normalized: list[float] = []
    for value in raw_bbox:
        if not isinstance(value, int | float):
            return None
        normalized.append(float(value))
    return normalized


def _normalize_string_list(raw_values: object) -> list[str]:
    if not isinstance(raw_values, list):
        return []
    return [value.strip() for value in raw_values if isinstance(value, str) and value.strip()]


def _build_document_ai_block(
    *,
    item: dict[str, Any],
    order: int,
    page_number: int,
) -> tuple[dict[str, Any] | None, str | None]:
    item_type = item.get("type")
    if not isinstance(item_type, str) or not item_type:
        return None, None

    if item_type == "discarded":
        return None, "discarded"

    block: dict[str, Any] = {
        "type": item_type,
        "pageNumber": page_number,
        "order": order,
        "source": {"artifact": "content_list"},
    }

    bbox = _normalize_bbox(item.get("bbox"))
    if bbox is not None:
        block["bbox"] = bbox

    if item_type == "text":
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            return None, None
        block["text"] = text.strip()
        text_level = item.get("text_level")
        if isinstance(text_level, int):
            block["textLevel"] = text_level
            block["role"] = "heading" if text_level == 1 else "paragraph"
        else:
            block["role"] = "paragraph"
        return block, "text"

    if item_type == "table":
        table_html = item.get("table_body")
        if isinstance(table_html, str) and table_html.strip():
            block["html"] = table_html.strip()
        captions = _normalize_string_list(item.get("table_caption"))
        if captions:
            block["caption"] = captions
        footnotes = _normalize_string_list(item.get("table_footnote"))
        if footnotes:
            block["footnote"] = footnotes
        image_path = item.get("img_path")
        if isinstance(image_path, str) and image_path.strip():
            block["imagePath"] = image_path.strip()
        return block, "table"

    if item_type == "image":
        image_path = item.get("img_path")
        if isinstance(image_path, str) and image_path.strip():
            block["imagePath"] = image_path.strip()
        captions = _normalize_string_list(item.get("image_caption"))
        if captions:
            block["caption"] = captions
        footnotes = _normalize_string_list(item.get("image_footnote"))
        if footnotes:
            block["footnote"] = footnotes
        return block, "image"

    text = item.get("text")
    if isinstance(text, str) and text.strip():
        block["text"] = text.strip()
    return block, item_type


def _collect_document_ai_structure(
    *,
    metadata: dict[str, Any],
    document_ai_output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    pages_map: dict[int, list[dict[str, Any]]] = {}
    flat_blocks: list[dict[str, Any]] = []
    stats = {
        "pageCount": 0,
        "blockCount": 0,
        "textBlockCount": 0,
        "tableCount": 0,
        "imageCount": 0,
        "discardedCount": 0,
    }
    warnings: list[dict[str, str]] = []

    def append_blocks(items: object, *, page_number_override: int | None = None) -> None:
        if not isinstance(items, list):
            warnings.append(
                {
                    "code": "content_list_invalid",
                    "detail": "document-ai content_list is not a JSON array",
                }
            )
            return

        for order, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                continue
            item_page_idx = raw_item.get("page_idx")
            page_number = page_number_override
            if page_number is None and isinstance(item_page_idx, int):
                page_number = item_page_idx + 1
            if page_number is None:
                page_number = 1

            block, block_kind = _build_document_ai_block(
                item=raw_item,
                order=order,
                page_number=page_number,
            )
            if block_kind == "discarded":
                stats["discardedCount"] += 1
                continue
            if block is None:
                continue

            stats["blockCount"] += 1
            if block_kind == "text":
                stats["textBlockCount"] += 1
            elif block_kind == "table":
                stats["tableCount"] += 1
            elif block_kind == "image":
                stats["imageCount"] += 1

            pages_map.setdefault(page_number, []).append(block)
            flat_blocks.append(block)

    def append_from_content_list_path(
        raw_path: object, *, page_number_override: int | None = None
    ) -> None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return
        content_list_path = Path(raw_path)
        if not content_list_path.is_absolute():
            content_list_path = (document_ai_output_dir / content_list_path).resolve()
        items = _read_json_file(content_list_path)
        if items is None:
            warnings.append(
                {
                    "code": "content_list_unreadable",
                    "detail": f"document-ai content_list could not be read: {content_list_path}",
                }
            )
            return
        append_blocks(items, page_number_override=page_number_override)

    outputs = metadata.get("outputs")
    if isinstance(outputs, dict):
        append_from_content_list_path(outputs.get("content_list"))

    page_results = metadata.get("page_results")
    if isinstance(page_results, list):
        for page_result in page_results:
            if not isinstance(page_result, dict):
                continue
            page_number = page_result.get("page_number")
            selected = page_result.get("selected")
            if not isinstance(page_number, int) or not isinstance(selected, dict):
                continue
            selected_outputs = selected.get("outputs")
            if isinstance(selected_outputs, dict):
                append_from_content_list_path(
                    selected_outputs.get("content_list"),
                    page_number_override=page_number,
                )

    pages = [
        {"pageNumber": page_number, "blocks": pages_map[page_number]}
        for page_number in sorted(pages_map)
    ]
    stats["pageCount"] = len(pages)
    return pages, flat_blocks, stats, warnings


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

        pages, structured_blocks, stats, warnings = _collect_document_ai_structure(
            metadata=metadata,
            document_ai_output_dir=document_ai_output_dir,
        )

        canonical_json = {
            "document": {
                "source": "document_ai",
                "filename": input_path.name,
                "parse_mode": metadata.get("parse_mode"),
                "artifacts": outputs,
            },
            "blocks": [
                {
                    "type": "text",
                    "text": markdown,
                    "format": "markdown",
                }
            ],
        }
        if pages:
            canonical_json["pages"] = pages
            canonical_json["blocks"].extend(structured_blocks)
            canonical_json["document"]["stats"] = stats
        if warnings:
            canonical_json["document"]["warnings"] = warnings
        return ParsedDocumentPayload(markdown=markdown, canonical_json=canonical_json)
