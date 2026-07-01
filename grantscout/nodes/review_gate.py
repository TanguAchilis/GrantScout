"""
Review-gate node — Human-in-the-Loop (HITL).

Role (per spec): present the drafted sections and PAUSE for a person to
edit/approve/reject before anything is marked finalized. Nothing is written to
state.finalized without explicit human approval. The agent NEVER submits an
application anywhere — it produces a draft for a human to use.

WHY ONLY THIS NODE WRITES state.finalized (least privilege)
-----------------------------------------------------------
Finalization is the one irreversible-feeling step ("this is ready to use"), so it
is gated behind a real human decision. The researcher/matcher/drafter write
working state (profile/matches/drafts) but are structurally unable to mark
anything finalized — that authority lives here and only here.

HOW THE PAUSE WORKS (ADK 2.0)
-----------------------------
On first execution `ctx.resume_inputs` is empty, so the node YIELDS a
RequestInput (interrupt_id="review") carrying the ReviewDecision schema and
returns — the workflow suspends. When the human responds (a function_response
keyed by "review"), the node re-runs (it is wrapped with rerun_on_resume=True in
agent.py) with `ctx.resume_inputs["review"]` populated, applies the decision, and
writes state.finalized. The node body deliberately avoids broad try/except so the
NodeInterruptedError that drives the pause can propagate.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput

from grantscout.models import Draft, ReviewDecision

INTERRUPT_ID = "review"
# Actionable HITL prompt: it names the decision the human can make (the fields of
# ReviewDecision) so the pause is self-explanatory in both the CLI and the web UI
# / ADK web console. Kept to a few short lines for readability.
REVIEW_MESSAGE = (
    "Review your draft sections before anything is finalized:\n"
    "  • approve the sections you want to keep,\n"
    "  • edit any section's text inline, and/or\n"
    "  • reject the ones you don't want.\n"
    "GrantScout will NOT submit anything — approved drafts are yours to use."
)


def apply_review_decision(drafts: list[Draft], decision: ReviewDecision) -> dict:
    """Pure function (unit-testable): turn drafts + a human decision into the
    finalized package. A section is finalized only if the human approved it and
    did not reject it; per-section edits override the draft content.

    The result is explicitly stamped `submitted: False` / `submitted_by_agent:
    False` — finalized means "ready for a human to use", never "sent"."""
    by_id = {d.id: d for d in drafts}
    finalized_sections: list[dict] = []
    for sid in decision.approved_section_ids:
        if sid in decision.rejected_ids:
            continue  # a reject always wins over an approve
        draft = by_id.get(sid)
        if not draft:
            continue
        content = decision.edits.get(sid, draft.content)
        finalized_sections.append(
            {
                "id": draft.id,
                "grant_id": draft.grant_id,
                "section_type": draft.section_type,
                "title": draft.title,
                "content": content,
                "edited_by_human": sid in decision.edits,
            }
        )
    return {
        "sections": finalized_sections,
        "approved_count": len(finalized_sections),
        "rejected_count": len(decision.rejected_ids),
        "reviewer_note": decision.note,
        # The hard, visible boundary: the agent never submits.
        "submitted": False,
        "submitted_by_agent": False,
        "disclaimer": "Draft prepared by GrantScout. Review and submit yourself; GrantScout never submits applications.",
    }


async def review_gate(ctx: Context) -> AsyncGenerator[Event, None]:
    """Pause for human review, then finalize the approved sections on resume."""
    # First pass: no human input yet -> request it and suspend the workflow.
    if not ctx.resume_inputs or INTERRUPT_ID not in ctx.resume_inputs:
        yield RequestInput(
            interrupt_id=INTERRUPT_ID,
            message=REVIEW_MESSAGE,
            response_schema=ReviewDecision,
        )
        return

    # Resume pass: a human has responded. Validate their decision against the
    # schema (reject malformed) and apply it.
    raw = ctx.resume_inputs[INTERRUPT_ID]
    decision = ReviewDecision.model_validate(raw if isinstance(raw, dict) else {})
    drafts = [Draft.model_validate(d) for d in (ctx.state.get("drafts") or [])]
    finalized = apply_review_decision(drafts, decision)

    yield Event(output=finalized, state={"finalized": finalized})
