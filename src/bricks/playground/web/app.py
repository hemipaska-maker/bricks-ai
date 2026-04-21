"""FastAPI application for the Bricks Playground web server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bricks.playground.web.routes import router

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

app = FastAPI(title="Bricks Playground", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(router)


@app.get("/")
async def index() -> FileResponse:
    """Serve the benchmark GUI frontend.

    Returns:
        FileResponse for the ``index.html`` single-page app.
    """
    return FileResponse(str(_INDEX_HTML))
