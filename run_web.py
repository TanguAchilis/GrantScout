"""
Launch the GrantScout local web UI.

    python run_web.py            # then open http://127.0.0.1:8000

Drives the same ADK 2.0 graph as the CLI. With a GOOGLE_API_KEY configured
(exported, or in a gitignored `.env` — loaded below), Gemini writes the draft
prose and match rationales; with no key the nodes fall back to deterministic
generation, so the catalog + eligibility + review-gate spine still runs fully
offline. Either way the agent NEVER submits anything — it drafts for a human.
"""
from __future__ import annotations

import os

import uvicorn

# Bridge `.env` -> os.environ BEFORE the app (and llm_available) is imported.
from grantscout.env import load_env

load_env()

HOST = os.environ.get("GRANTSCOUT_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("GRANTSCOUT_WEB_PORT", "8000"))

if __name__ == "__main__":
    from grantscout.config import MODEL
    from grantscout.llm import llm_available

    mode = f"Gemini live ({MODEL})" if llm_available() else "offline deterministic fallback (no API key)"
    print(f"GrantScout web UI -> http://{HOST}:{PORT}  (Ctrl+C to stop)")
    print(f"LLM prose path: {mode}")
    uvicorn.run("web.server:application", host=HOST, port=PORT, log_level="info")
