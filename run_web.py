"""
Launch the GrantScout local web UI.

    python run_web.py            # then open http://127.0.0.1:8000

Runs entirely offline (no cloud, no API key) and drives the same ADK 2.0 graph as
the CLI. The agent NEVER submits anything — it drafts for a human to use.
"""
from __future__ import annotations

import os

import uvicorn

HOST = os.environ.get("GRANTSCOUT_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("GRANTSCOUT_WEB_PORT", "8000"))

if __name__ == "__main__":
    print(f"GrantScout web UI -> http://{HOST}:{PORT}  (Ctrl+C to stop)")
    uvicorn.run("web.server:application", host=HOST, port=PORT, log_level="info")
