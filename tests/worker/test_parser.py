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


def test_document_ai_parser_builds_structured_canonical_json_from_content_list(tmp_path) -> None:
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
        document_ai_output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = document_ai_output_dir / "result.md"
        markdown_path.write_text("# heading\n\nbody")
        content_list_path = document_ai_output_dir / "content_list.json"
        content_list_path.write_text(
            json.dumps(
                [
                    {
                        "type": "text",
                        "text": "Heading",
                        "text_level": 1,
                        "bbox": [1, 2, 3, 4],
                        "page_idx": 0,
                    },
                    {
                        "type": "table",
                        "table_body": "<table><tr><td>A</td></tr></table>",
                        "table_caption": ["Summary table"],
                        "bbox": [10, 20, 30, 40],
                        "page_idx": 0,
                    },
                    {
                        "type": "discarded",
                        "text": "noise",
                        "bbox": [0, 0, 1, 1],
                        "page_idx": 0,
                    },
                ]
            )
        )
        (document_ai_output_dir / "meta.json").write_text(
            json.dumps(
                {
                    "parse_mode": "rasterized",
                    "outputs": {
                        "markdown": str(markdown_path),
                        "content_list": str(content_list_path),
                    },
                }
            )
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    original_run = subprocess.run
    subprocess.run = fake_run
    try:
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        subprocess.run = original_run

    assert parsed.markdown == "# heading\n\nbody"
    assert parsed.canonical_json["document"]["parse_mode"] == "rasterized"
    assert parsed.canonical_json["document"]["stats"] == {
        "pageCount": 1,
        "blockCount": 2,
        "textBlockCount": 1,
        "tableCount": 1,
        "imageCount": 0,
        "discardedCount": 1,
    }
    assert parsed.canonical_json["blocks"][0] == {
        "type": "text",
        "text": "# heading\n\nbody",
        "format": "markdown",
    }
    assert parsed.canonical_json["pages"][0]["pageNumber"] == 1
    assert parsed.canonical_json["pages"][0]["blocks"][0]["role"] == "heading"
    assert parsed.canonical_json["pages"][0]["blocks"][1]["type"] == "table"
    assert parsed.canonical_json["pages"][0]["blocks"][1]["caption"] == ["Summary table"]


def test_document_ai_parser_reads_page_adaptive_content_lists(tmp_path) -> None:
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
        document_ai_output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = document_ai_output_dir / "selected.md"
        markdown_path.write_text("page 1\n\npage 2")
        page_one_list = document_ai_output_dir / "page1_content_list.json"
        page_one_list.write_text(json.dumps([{"type": "text", "text": "Page one", "page_idx": 0}]))
        page_two_list = document_ai_output_dir / "page2_content_list.json"
        page_two_list.write_text(json.dumps([{"type": "text", "text": "Page two", "page_idx": 0}]))
        (document_ai_output_dir / "meta.json").write_text(
            json.dumps(
                {
                    "parse_mode": "page_adaptive",
                    "outputs": {"selected_markdown": str(markdown_path)},
                    "page_results": [
                        {
                            "page_number": 1,
                            "selected": {"outputs": {"content_list": str(page_one_list)}},
                        },
                        {
                            "page_number": 2,
                            "selected": {"outputs": {"content_list": str(page_two_list)}},
                        },
                    ],
                }
            )
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    original_run = subprocess.run
    subprocess.run = fake_run
    try:
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        subprocess.run = original_run

    assert [page["pageNumber"] for page in parsed.canonical_json["pages"]] == [1, 2]
    assert parsed.canonical_json["pages"][0]["blocks"][0]["text"] == "Page one"
    assert parsed.canonical_json["pages"][1]["blocks"][0]["text"] == "Page two"


def test_document_ai_parser_falls_back_when_content_list_is_invalid(tmp_path) -> None:
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
        document_ai_output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = document_ai_output_dir / "result.md"
        markdown_path.write_text("# parsed")
        content_list_path = document_ai_output_dir / "content_list.json"
        content_list_path.write_text("not-json")
        (document_ai_output_dir / "meta.json").write_text(
            json.dumps(
                {
                    "outputs": {
                        "markdown": str(markdown_path),
                        "content_list": str(content_list_path),
                    }
                }
            )
        )
        return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

    original_run = subprocess.run
    subprocess.run = fake_run
    try:
        parsed = parser.parse(input_path=input_path, output_dir=output_dir)
    finally:
        subprocess.run = original_run

    assert "pages" not in parsed.canonical_json
    assert parsed.canonical_json["blocks"] == [
        {"type": "text", "text": "# parsed", "format": "markdown"}
    ]
    assert parsed.canonical_json["document"]["warnings"][0]["code"] == "content_list_unreadable"
