import json
import subprocess

from src.worker import document_ai_entrypoint
from src.worker.document_ai_entrypoint import (
    EntrypointError,
    _build_canonical_json,
    _build_parser,
    _resolve_markdown_path,
    run_entrypoint,
)


def test_resolve_markdown_path_uses_selected_markdown_in_metadata(tmp_path) -> None:
    markdown_path = tmp_path / "selected_markdown.md"
    markdown_path.write_text("# parsed", encoding="utf-8")

    metadata = {
        "outputs": {
            "selected_markdown": str(markdown_path),
        }
    }

    resolved = _resolve_markdown_path(tmp_path, metadata)
    assert resolved == markdown_path


def test_resolve_markdown_path_rejects_path_outside_output_dir(tmp_path) -> None:
    outside_path = tmp_path.parent / "outside.md"
    outside_path.write_text("outside", encoding="utf-8")
    metadata = {
        "outputs": {
            "selected_markdown": str(outside_path),
        }
    }

    try:
        _resolve_markdown_path(tmp_path, metadata)
    except EntrypointError as exc:
        assert "missing markdown content" in str(exc)
    else:
        raise AssertionError("expected EntrypointError")


def test_resolve_markdown_path_raises_when_missing(tmp_path) -> None:
    metadata = {"outputs": {}}

    try:
        _resolve_markdown_path(tmp_path, metadata)
    except EntrypointError as exc:
        assert "missing markdown content" in str(exc)
    else:
        raise AssertionError("expected EntrypointError")


def test_load_json_wraps_decode_error(tmp_path) -> None:
    from src.worker.document_ai_entrypoint import _load_json

    json_path = tmp_path / "meta.json"
    json_path.write_text("{invalid", encoding="utf-8")

    try:
        _load_json(json_path)
    except EntrypointError as exc:
        assert "failed to load JSON" in str(exc)
    else:
        raise AssertionError("expected EntrypointError")


def test_build_parser_uses_absolute_default_parse_script_path() -> None:
    parser = _build_parser()
    args = parser.parse_args(["/tmp/input.pdf", "/tmp/out"])
    assert str(args.parse_script).startswith("/")
    assert args.parse_script.endswith("vendor/document-ai/scripts/parse_document.py")


def test_build_canonical_json_contains_document_and_blocks(tmp_path) -> None:
    input_path = tmp_path / "sample.pdf"
    input_path.write_bytes(b"%PDF-sample")

    metadata = {
        "parse_mode": "page_adaptive",
        "language": "ko",
        "inspection": {"suspicious": False},
        "outputs": {"selected_markdown": "/tmp/out/selected_markdown.md"},
    }

    canonical = _build_canonical_json(
        metadata=metadata,
        input_path=input_path,
        markdown_text="# title\n\nbody",
    )

    assert canonical["document"]["source"] == "document_ai"
    assert canonical["document"]["filename"] == "sample.pdf"
    assert canonical["blocks"][0]["type"] == "text"
    assert "body" in canonical["blocks"][0]["text"]
    # Ensure the structure remains JSON serializable for result.json writes.
    json.dumps(canonical)


def test_run_entrypoint_writes_worker_contract_files(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    input_path = tmp_path / "sample.pdf"
    output_dir = tmp_path / "out"
    parse_script = tmp_path / "parse_document.py"
    input_path.write_bytes(b"%PDF-sample")
    parse_script.write_text("print('placeholder')", encoding="utf-8")

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "selected_markdown.md"
        markdown_path.write_text("# parsed", encoding="utf-8")
        metadata = {
            "parse_mode": "page_adaptive",
            "language": "ko",
            "inspection": {"suspicious": False},
            "outputs": {"selected_markdown": str(markdown_path)},
        }
        (output_dir / "meta.json").write_text(json.dumps(metadata), encoding="utf-8")
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(document_ai_entrypoint.subprocess, "run", fake_run)
    run_entrypoint(
        input_path=input_path,
        output_dir=output_dir,
        parse_script=parse_script,
        language="ko",
        page_adaptive=True,
        timeout_seconds=60,
    )

    result_md = output_dir / "result.md"
    result_json = output_dir / "result.json"
    assert result_md.exists()
    assert result_json.exists()
    assert result_md.read_text(encoding="utf-8") == "# parsed"
    result_payload = json.loads(result_json.read_text(encoding="utf-8"))
    assert result_payload["document"]["source"] == "document_ai"
