"""
Thin LLM helper.

WHY THIS WRAPPER EXISTS
-----------------------
The three reasoning nodes (researcher, matcher, drafter) use an LLM ONLY for
prose — extracting narrative, explaining gaps in plain language, and writing
draft sections. Every *decision* (eligibility pass/fail, ranking) is made by
deterministic Python elsewhere. This wrapper isolates the single place a model
is called, so:

  * Phase 1 runs fully OFFLINE: with no API key configured, `complete()` returns
    None and each node uses its deterministic fallback. The catalog + eligibility
    + review-gate spine still runs end-to-end and the tests stay hermetic.
  * Phase 2 (Antigravity) only has to provide a real key/ADC — no node code
    changes — and the LLM path lights up automatically.

The key is read from the environment (never hardcoded); see security.py / config.
"""
from __future__ import annotations

import os

from grantscout.config import MODEL


def llm_available() -> bool:
    """True only if a credential is configured AND the google-genai SDK imports.

    We check the environment for either an AI Studio API key or Vertex ADC config.
    No key -> we stay in deterministic mode (Phase 1)."""
    has_key = bool(os.environ.get("GOOGLE_API_KEY")) or (
        os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
        and bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    )
    if not has_key:
        return False
    try:
        import google.genai  # noqa: F401
    except Exception:
        return False
    return True


def complete(prompt: str, *, system: str | None = None) -> str | None:
    """Return model text, or None if the LLM is unavailable (caller falls back).

    PHASE 2 (Antigravity): this real Gemini call path is only EXERCISED once a
    key/ADC is configured. In Phase 1 there is no key, so this returns None and
    the deterministic fallbacks run. The code is left in place (guarded) so
    Phase 2 needs zero node changes to enable it.
    """
    if not llm_available():
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        contents = prompt if system is None else f"{system}\n\n{prompt}"
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return (resp.text or "").strip() or None
    except Exception:
        # Never let an LLM/network error break the deterministic spine. We do NOT
        # swallow node-control exceptions here — this is an isolated helper, not a
        # node body, so catching broadly is safe and keeps the pipeline running.
        return None
