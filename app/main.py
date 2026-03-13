from fastapi import FastAPI


app = FastAPI(
    title="document-agent-api",
    version="0.1.0",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "document-agent-api",
        "version": "0.1.0",
    }
