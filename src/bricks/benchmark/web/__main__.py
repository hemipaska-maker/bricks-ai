"""Entry point for the Bricks Benchmark web server.

Run with:
    python -m bricks.benchmark.web
"""

from __future__ import annotations

import uvicorn

from bricks.benchmark.web.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8742)  # noqa: S104
