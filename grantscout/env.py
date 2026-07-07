"""
Minimal `.env` loader — no python-dotenv dependency.

WHY THIS EXISTS
---------------
`.env.example` tells users to copy their key into a gitignored `.env`, and the
README says setting GOOGLE_API_KEY "lights up the LLM prose path". But library
code deliberately reads credentials from os.environ only (see llm.py) — so
without a bridge, a key sitting in `.env` was silently ignored and the app ran
in deterministic-fallback mode even when the user thought Gemini was on.

The two local entrypoints (run_web.py, run_local.py) call load_env() before
anything checks llm_available(). Real environment variables always win: values
already present in os.environ are never overwritten, so `GOOGLE_API_KEY=... `
exported in the shell still takes precedence over the file.
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env(path: str | os.PathLike | None = None) -> int:
    """Load KEY=VALUE lines from `.env` (repo root by default) into os.environ.

    Skips comments, blank lines, and untouched placeholders from .env.example
    (values starting with "your-"). Never overwrites variables already set in
    the environment. Returns the number of variables set; a missing file is
    fine (0) — the app then runs in its offline deterministic mode.
    """
    env_file = Path(path) if path is not None else _REPO_ROOT / ".env"
    if not env_file.is_file():
        return 0
    loaded = 0
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not key or not value or value.startswith("your-"):
            continue
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


__all__ = ["load_env"]
