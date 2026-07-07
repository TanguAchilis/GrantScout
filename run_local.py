"""
GrantScout local runner — runs ONE full pipeline turn locally.

    researcher -> matcher -> drafter -> [PAUSE: human review] -> finalize

It drives the real ADK 2.0 Workflow graph via InMemoryRunner: it streams the
first pass until the review gate suspends (an `adk_request_input` interrupt),
SIMULATES a human approval (a function_response keyed by the interrupt id), then
resumes to finalize. With a GOOGLE_API_KEY (exported or in `.env`) Gemini writes
the prose; with no key it runs fully offline on deterministic fallbacks. It
never submits anything either way.

Run:
    python run_local.py            # add GRANTSCOUT_FORCE_COLOR=1 to force color when piped

Prefer clicking around instead of reading a script? Run the web UI:
    python run_web.py              # then open http://127.0.0.1:8000

What to watch for (the demo's whole point — eligibility HONESTY):
    a grant that is a perfect FOCUS fit can be ranked BELOW a weaker-fit grant
    because the org is not yet ELIGIBLE for it — and the exact gaps are shown.
"""
from __future__ import annotations

import asyncio
import warnings

# Bridge `.env` -> os.environ before any grantscout module checks credentials.
from grantscout.env import load_env

load_env()

from google.genai import types

from grantscout import ui
from grantscout.agent import app
from grantscout.models import OrgInput, ReviewDecision

# ResumabilityConfig is flagged experimental in ADK 2.3; the warning is expected.
warnings.filterwarnings("ignore", message=".*ResumabilityConfig.*")

USER_ID = "local_user"
MARKER = "[ORG TO PROVIDE]"

# A realistic sample org chosen to SHOW the honesty mechanism: a 2-year-old,
# registered, board-governed Kenyan health/WASH NGO WITHOUT audited accounts.
# Result: it is eligible for several funders, but the two perfect-focus-fit WASH
# funders (which require 3+ years AND audited accounts) come back as "gaps" and
# are correctly ranked lower.
SAMPLE_ORG = OrgInput(
    name="Maji Bora Community Initiative",
    org_type="ngo_cbo",
    country="Kenya",
    focus_areas=["health", "WASH"],  # 'WASH' is normalized to water_sanitation
    mission="We improve community health by expanding access to clean water and sanitation in rural Kenya.",
    years_operating=2,
    registered=True,
    has_board=True,
    has_audited_accounts=False,  # <- the gap that keeps the perfect-fit grants out of reach
    budget_band="$50k-$250k",
)


async def _get_state(runner, session_id) -> dict:
    sess = await runner.session_service.get_session(
        app_name=app.name, user_id=USER_ID, session_id=session_id
    )
    return dict(sess.state)


def _print_org(org: OrgInput) -> None:
    ui.section("Organization")
    facts = [
        ("Type", "NGO / CBO" if org.org_type == "ngo_cbo" else "Startup / social enterprise"),
        ("Country", org.country),
        ("Focus", ", ".join(org.focus_areas)),
        ("Years operating", str(org.years_operating)),
        ("Registered", "yes" if org.registered else "no"),
        ("Board", "yes" if org.has_board else "no"),
        ("Audited accounts", "yes" if org.has_audited_accounts else "no"),
    ]
    print(f"  {ui.paint(org.name, ui.BOLD)}")
    for label, value in facts:
        print(f"  {ui.paint(ui.pad(label + ':', 18), ui.DIM)}{value}")


def _print_matches(matches: list[dict]) -> None:
    ui.section("Ranked matches")
    ui.note("  Fit and eligibility are scored separately — grants you can WIN come first.")
    prev_status = None
    for m in matches:
        status = m["eligibility_status"]
        if status != prev_status:
            ui.group_header(status)
            prev_status = status
        color = ui.status_color(status)
        fit = f"{m['fit_score']:.0%}"
        title = ui.truncate(m["grant"]["title"], ui.WIDTH - 12)
        bar = ui.paint("▎", color)
        callout = ""
        if status == "gaps" and m["fit_score"] >= 0.99:
            callout = ui.paint("  ← perfect fit, not yet eligible", color)
        print(f"   {bar} {ui.pad(fit, 4, 'right')}  {title}{callout}")
        for gap in m["gaps"]:
            print(f"        {ui.paint('↳ ' + gap, ui.DIM)}")
    print()


def _print_drafts(drafts: list[dict]) -> None:
    total_markers = sum(d["content"].count(MARKER) for d in drafts)
    ui.section("Draft sections")
    ui.note(
        f"  {len(drafts)} sections · {total_markers} {MARKER} markers to fill with real figures."
    )
    for d in drafts:
        n = d["content"].count(MARKER)
        badge = ui.paint(f"[{n} to fill]", ui.AMBER) if n else ui.paint("[ready]", ui.GREEN)
        print()
        print(f"  {ui.paint(d['title'], ui.BOLD)}  {badge}")
        print(f"  {ui.paint(d['id'], ui.GREY)}")
        for row in d["content"].splitlines():
            print(f"    {ui.highlight_markers(row)}")
    print()


def _print_finalized(finalized: dict) -> None:
    status = ui.paint("● NOT SUBMITTED", ui.BOLD, ui.GREEN)
    ui.section("Finalized package")
    print(
        f"  {status}    "
        f"approved {ui.paint(str(finalized['approved_count']), ui.BOLD)} · "
        f"edited {sum(1 for s in finalized['sections'] if s['edited_by_human'])} · "
        f"rejected {finalized['rejected_count']}"
    )
    if finalized.get("reviewer_note"):
        print(f'  {ui.paint("note:", ui.DIM)} “{finalized["reviewer_note"]}”')
    print()
    print(ui.paint("  Sections ready for your use:", ui.BOLD))
    for i, s in enumerate(finalized["sections"], 1):
        edited = ui.paint(" (edited)", ui.CYAN) if s["edited_by_human"] else ""
        print(f"    {i}. {s['title']}{edited}")
    remaining = sum(s["content"].count(MARKER) for s in finalized["sections"])
    print()
    print(ui.paint("  Next steps:", ui.BOLD))
    print(f"    • Fill the {remaining} remaining {MARKER} markers with real figures")
    print("    • Verify each grant's deadline & terms at its source URL")
    print(f"    • {ui.paint('Submit the applications yourself', ui.BOLD)} — GrantScout never submits")


async def main() -> None:
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name=app.name, user_id=USER_ID)

    ui.banner("GrantScout", "local pipeline run — offline · no cloud · never submits")
    _print_org(SAMPLE_ORG)

    # ----- PASS 1: run until the review gate suspends -----------------------
    print()
    ui.step("Running researcher → matcher → drafter …")
    start_msg = types.Content(role="user", parts=[types.Part.from_text(text=SAMPLE_ORG.model_dump_json())])
    interrupt_id = fc_name = None
    async for ev in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=start_msg):
        if isinstance(ev.output, str):
            print(f"    {ui.paint('·', ui.DIM)} {ev.output}")
        for fc in (ev.get_function_calls() or []):
            if fc.name == "adk_request_input":
                interrupt_id, fc_name = fc.id, fc.name

    state = await _get_state(runner, session.id)
    _print_matches(state.get("matches", []))
    drafts = state.get("drafts", [])
    _print_drafts(drafts)

    if interrupt_id is None:
        raise RuntimeError("Pipeline did not reach the review gate — expected an interrupt.")
    assert state.get("finalized") is None, "Nothing should be finalized before human approval."

    ui.section("Human review gate")
    print(f"  {ui.paint('⏸ PAUSED', ui.BOLD, ui.AMBER)} — awaiting a human decision (interrupt id: {interrupt_id})")
    ui.note("  Nothing is finalized until a person approves. Simulating an approval now…")

    # ----- SIMULATE the human decision -------------------------------------
    approved_ids = [d["id"] for d in drafts]
    edits = {}
    if approved_ids:
        edits[approved_ids[0]] = drafts[0]["content"] + "\n\n[Human edit] We serve 12 villages in Kitui County."
    decision = ReviewDecision(
        approved_section_ids=approved_ids,
        edits=edits,
        rejected_ids=[],
        note="Approved with one factual edit; will fill remaining [ORG TO PROVIDE] markers before use.",
    )

    # ----- PASS 2: resume with the decision -> finalize --------------------
    resume_msg = types.Content(
        role="user",
        parts=[types.Part(function_response=types.FunctionResponse(
            id=interrupt_id, name=fc_name, response=decision.model_dump()))],
    )
    async for _ in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=resume_msg):
        pass

    final_state = await _get_state(runner, session.id)
    _print_finalized(final_state["finalized"])
    print()
    print(ui.rule("━"))
    print(ui.paint("✓ One full pipeline turn completed "
                   "(researcher → matcher → drafter → review gate → finalize).", ui.GREEN))
    print()


if __name__ == "__main__":
    asyncio.run(main())
