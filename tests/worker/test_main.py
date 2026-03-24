from pathlib import Path

import pytest

from src.worker import main as worker_main
from src.worker.parser import DocumentAIParser


def test_build_parsers_requires_document_ai_script_path_when_enabled(monkeypatch) -> None:
    class SettingsStub:
        enabled_parser_backends = ["markitdown", "document_ai"]
        pdftotext_command = "pdftotext"
        parser_timeout_seconds = 30
        document_ai_script_path = None

    monkeypatch.setattr(worker_main, "get_settings", lambda: SettingsStub())

    with pytest.raises(RuntimeError, match="document_ai_script_path is required"):
        worker_main._build_parsers()


def test_build_parsers_includes_document_ai_when_script_path_is_set(monkeypatch, tmp_path) -> None:
    script_path = tmp_path / "parse_document.py"
    script_path.write_text("print('ok')")

    class SettingsStub:
        enabled_parser_backends = ["markitdown", "document_ai"]
        pdftotext_command = "pdftotext"
        parser_timeout_seconds = 30
        document_ai_script_path = str(script_path)

    monkeypatch.setattr(worker_main, "get_settings", lambda: SettingsStub())

    parsers = worker_main._build_parsers()
    parser = parsers["document_ai"]

    assert "document_ai" in parsers
    assert isinstance(parser, DocumentAIParser)
    assert Path(parser.script_path) == script_path
