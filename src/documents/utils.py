def sanitize_document_filename(filename: str) -> str:
    normalized = filename.strip().replace("\\", "/")
    if not normalized:
        return "uploaded.bin"

    leaf = normalized.split("/")[-1].strip()
    if not leaf or leaf in {".", ".."}:
        return "uploaded.bin"
    return leaf
