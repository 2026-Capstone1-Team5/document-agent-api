from src.worker.parser import DocumentAiCliParser, WorkerParseError


def test_document_ai_cli_parser_reads_result_files(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    command = """python -c "from pathlib import Path; import json; out=Path(r'{output_dir}'); (out / 'result.md').write_text('# title', encoding='utf-8'); (out / 'result.json').write_text(json.dumps({{'document': {{'title': 'title'}}}}), encoding='utf-8')" """  # noqa: E501
    parser = DocumentAiCliParser(command_template=command, timeout_seconds=30)

    parsed = parser.parse(input_path=input_path, output_dir=output_dir)

    assert parsed.markdown == "# title"
    assert parsed.canonical_json["document"]["title"] == "title"


def test_document_ai_cli_parser_raises_when_result_files_are_missing(tmp_path) -> None:
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    input_path.write_bytes(b"%PDF-test")
    output_dir.mkdir()

    parser = DocumentAiCliParser(
        command_template="python -c \"print('ok')\"",
        timeout_seconds=30,
    )

    try:
        parser.parse(input_path=input_path, output_dir=output_dir)
    except WorkerParseError as exc:
        assert "result.md or result.json" in str(exc)
    else:
        raise AssertionError("expected WorkerParseError")
