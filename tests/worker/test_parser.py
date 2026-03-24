import json
import subprocess
import sys
import types
from unittest.mock import Mock

from src.worker.parser import (
    DocumentAIParser,
    MarkItDownParser,
    PdftotextParser,
    WorkerParseError,
)


def test_markitdown_parser_reads_text_content(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    fake_module = types.ModuleType("markitdown")

    class FakeResult:
        text_content = "# title\n\nbody"

    class FakeMarkItDown:
        def __init__(self, *, enable_plugins: bool) -> None:
            assert enable_plugins is False

        def convert(self, source: str) -> FakeResult:
            assert source == str(input_path)
            return FakeResult()

    setattr(fake_module, "MarkItDown", FakeMarkItDown)
    original_module = sys.modules.get("markitdown")
    sys.modules["markitdown"] = fake_module

    try:
        parser = MarkItDownParser()
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        if original_module is None:
            del sys.modules["markitdown"]
        else:
            sys.modules["markitdown"] = original_module

    assert parsed.markdown == "# title\n\nbody"
    assert parsed.canonical_json["document"]["source"] == "markitdown"
    assert parsed.canonical_json["blocks"][0]["text"] == "# title\n\nbody"


def test_markitdown_parser_raises_for_empty_text(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    fake_module = types.ModuleType("markitdown")

    class FakeResult:
        text_content = " \n"

    class FakeMarkItDown:
        def __init__(self, *, enable_plugins: bool) -> None:
            assert enable_plugins is False

        def convert(self, source: str) -> FakeResult:
            assert source == str(input_path)
            return FakeResult()

    setattr(fake_module, "MarkItDown", FakeMarkItDown)
    original_module = sys.modules.get("markitdown")
    sys.modules["markitdown"] = fake_module

    try:
        parser = MarkItDownParser()
        try:
            parser.parse(input_path=input_path, output_dir=output_dir)
        except WorkerParseError as exc:
            assert "markitdown returned no extractable text" in str(exc)
        else:
            raise AssertionError("expected WorkerParseError")
    finally:
        if original_module is None:
            del sys.modules["markitdown"]
        else:
            sys.modules["markitdown"] = original_module


def test_pdftotext_parser_reads_stdout(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    parser = PdftotextParser(command="pdftotext", timeout_seconds=30)
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=["pdftotext", "-layout", str(input_path), "-"],
            returncode=0,
            stdout="hello\nworld\n",
            stderr="",
        )
    )

    original_run = subprocess.run
    subprocess.run = run
    try:
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        subprocess.run = original_run

    assert parsed.markdown == "hello\nworld"
    assert parsed.canonical_json["document"]["source"] == "pdftotext"
    assert parsed.canonical_json["blocks"][0]["text"] == "hello\nworld"


def test_pdftotext_parser_raises_for_empty_text(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    parser = PdftotextParser(command="pdftotext", timeout_seconds=30)
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=["pdftotext", "-layout", str(input_path), "-"],
            returncode=0,
            stdout=" \n",
            stderr="",
        )
    )

    original_run = subprocess.run
    subprocess.run = run
    try:
        try:
            parser.parse(input_path=input_path, output_dir=output_dir)
        except WorkerParseError as exc:
            assert "no extractable text" in str(exc)
        else:
            raise AssertionError("expected WorkerParseError")
    finally:
        subprocess.run = original_run


def test_document_ai_parser_reads_relative_markdown_output(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    script_path = tmp_path / "parse_document.py"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()
    script_path.write_text("# stub")

    parser = DocumentAIParser(script_path=str(script_path), timeout_seconds=30)

    def fake_run(*args, **kwargs):
        del args, kwargs
        document_ai_output_dir = output_dir / "document_ai_output"
        nested_dir = document_ai_output_dir / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = nested_dir / "result.md"
        markdown_path.write_text("# parsed")
        (document_ai_output_dir / "meta.json").write_text(
            json.dumps({"outputs": {"markdown": "nested/result.md"}})
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    original_run = subprocess.run
    subprocess.run = fake_run
    try:
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        subprocess.run = original_run

    assert parsed.markdown == "# parsed"
    assert parsed.canonical_json["document"]["source"] == "document_ai"
