"""
GrantScout web UI — Starlette backend.

This serves a single-page interface (web/static/) and exposes a thin JSON API that
drives the SAME ADK 2.0 Workflow graph the CLI uses (Gemini prose when a key is
configured, deterministic fallback otherwise):

    POST /api/run       {OrgInput}            -> runs researcher->matcher->drafter,
                                                 pauses at the review gate, returns
                                                 matches + drafts + a session id.
    POST /api/finalize  {session_id, decision}-> resumes the gate with the human's
                                                 ReviewDecision, returns the
                                                 finalized (never-submitted) package.
    GET  /api/meta                            -> vocab for the form (focus areas, org types).

The HITL pause is real: /api/run streams until the workflow suspends at the
`adk_request_input` interrupt; /api/finalize sends the matching function_response
to resume it. Runner instances are held in-memory per session so the resume lands
on the same suspended workflow.

Security note: input is validated via the same Pydantic models the graph uses; the
web handlers convert validation errors into 400s (catching here is fine — these
are HTTP boundary handlers, not ADK node bodies).
"""
from __future__ import annotations

import pathlib
import warnings

import re

from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

# Silence the expected experimental-feature warning at import time.
warnings.filterwarnings("ignore", message=".*ResumabilityConfig.*")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from grantscout.agent import app as adk_app  # noqa: E402
from grantscout.config import FOCUS_AREAS, MODEL, ORG_TYPES  # noqa: E402
from grantscout.llm import llm_available  # noqa: E402
from grantscout.models import OrgInput, ReviewDecision  # noqa: E402
from grantscout.nodes.review_gate import REVIEW_MESSAGE  # noqa: E402

STATIC_DIR = pathlib.Path(__file__).parent / "static"
USER_ID = "web_user"

# session_id -> {runner, interrupt_id, fc_name}. In-memory only (single-process
# local tool); a real deployment would use a shared session service (Phase 2).
_SESSIONS: dict[str, dict] = {}


async def _session_state(runner: InMemoryRunner, session_id: str) -> dict:
    sess = await runner.session_service.get_session(
        app_name=adk_app.name, user_id=USER_ID, session_id=session_id
    )
    return dict(sess.state)


async def index(request):
    return FileResponse(STATIC_DIR / "index.html")


async def meta(request):
    """Form vocabularies (sorted for stable display) + which LLM mode is active,
    so the UI badge can say honestly whether Gemini is writing the prose."""
    live = llm_available()
    return JSONResponse(
        {
            "focus_areas": sorted(FOCUS_AREAS),
            "org_types": sorted(ORG_TYPES),
            "llm_live": live,
            "model": MODEL if live else None,
        }
    )


async def api_run(request):
    try:
        payload = await request.json()
        # Re-drafting (a new grant selection) reuses this endpoint; the client
        # sends the old session id so we can free it. Not part of OrgInput.
        replace_session_id = payload.pop("replace_session_id", None)
        org = OrgInput.model_validate(payload)
    except Exception as exc:  # HTTP boundary: turn bad input into a 400
        return JSONResponse({"error": f"Invalid organization details: {exc}"}, status_code=400)

    if replace_session_id:
        _SESSIONS.pop(replace_session_id, None)

    runner = InMemoryRunner(app=adk_app)
    session = await runner.session_service.create_session(app_name=adk_app.name, user_id=USER_ID)

    start_msg = types.Content(role="user", parts=[types.Part.from_text(text=org.model_dump_json())])
    interrupt_id = fc_name = None
    async for ev in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=start_msg):
        for fc in (ev.get_function_calls() or []):
            if fc.name == "adk_request_input":
                interrupt_id, fc_name = fc.id, fc.name

    if interrupt_id is None:
        return JSONResponse({"error": "Pipeline did not reach the review gate."}, status_code=500)

    state = await _session_state(runner, session.id)
    _SESSIONS[session.id] = {"runner": runner, "interrupt_id": interrupt_id, "fc_name": fc_name}
    return JSONResponse(
        {
            "session_id": session.id,
            "org_profile": state.get("org_profile"),
            "matches": state.get("matches", []),
            "drafts": state.get("drafts", []),
            "selected_grant_ids": state.get("selected_grant_ids", []),
            "review_message": REVIEW_MESSAGE,
        }
    )


async def api_finalize(request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Malformed request body."}, status_code=400)

    session_id = payload.get("session_id")
    sess = _SESSIONS.get(session_id)
    if not sess:
        return JSONResponse({"error": "Unknown or expired session. Please run again."}, status_code=404)

    try:
        decision = ReviewDecision.model_validate(payload.get("decision") or {})
    except Exception as exc:
        return JSONResponse({"error": f"Invalid review decision: {exc}"}, status_code=400)

    runner = sess["runner"]
    resume_msg = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=sess["interrupt_id"], name=sess["fc_name"], response=decision.model_dump()
                )
            )
        ],
    )
    async for _ in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=resume_msg):
        pass

    state = await _session_state(runner, session_id)
    # One-shot: drop the session after finalizing to free memory.
    _SESSIONS.pop(session_id, None)
    return JSONResponse({"finalized": state.get("finalized")})


_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def api_export(request):
    """Build a Word (.docx) file from drafted/finalized sections and return it as a
    download. The client sends sections pre-grouped by grant so this handler needs
    no session/catalog lookups."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Malformed request body."}, status_code=400)

    org_name = payload.get("org_name") or ""
    groups = payload.get("groups") or []
    finalized = bool(payload.get("finalized"))
    # Sanitize the client-supplied filename (prevents header injection / odd names).
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", str(payload.get("filename") or "grantscout"))
    if not filename.lower().endswith(".docx"):
        filename += ".docx"

    try:
        from web.docx_export import build_docx

        data = build_docx(org_name, groups, finalized)
    except Exception as exc:  # HTTP boundary
        return JSONResponse({"error": f"Could not build document: {exc}"}, status_code=500)

    return Response(
        content=data,
        media_type=_DOCX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


application = Starlette(
    routes=[
        Route("/", index),
        Route("/api/meta", meta),
        Route("/api/run", api_run, methods=["POST"]),
        Route("/api/finalize", api_finalize, methods=["POST"]),
        Route("/api/export", api_export, methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
)
