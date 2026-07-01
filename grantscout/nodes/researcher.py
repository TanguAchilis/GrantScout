"""
Researcher node (graph entry).

Role (per spec): build a structured org profile capturing exactly the facts
funders screen on, because the matcher scores against them — org_type, country,
registration, years_operating, has_board, has_audited_accounts, revenue_model,
mission, focus_areas, budget_band.

This is the spec's `kind: llm_agent` node. In Phase 1 it is implemented as a
FUNCTION node that normalizes structured input deterministically and uses the LLM
only to polish the mission summary when a key is available. (See agent.py for why
the reasoning nodes are function nodes rather than raw LlmAgent — the short
version: it keeps the eligibility decision in deterministic Python and lets the
whole graph run offline.)

Security: PII is scrubbed from free text BEFORE it could ever reach a model or a
trace (least surprise: the very first node sanitizes).
"""
from __future__ import annotations

from google.adk.agents.context import Context
from google.adk.events.event import Event

from grantscout.llm import complete
from grantscout.models import OrgInput, OrgProfile
from grantscout.security import pii_scrub

# Small synonym map -> canonical focus areas. Unknown terms pass through (lowered)
# so they can still overlap with catalog focus areas.
_FOCUS_SYNONYMS = {
    "wash": "water_sanitation",
    "water": "water_sanitation",
    "sanitation": "water_sanitation",
    "fintech": "financial_inclusion",
    "finance": "financial_inclusion",
    "agritech": "agriculture",
    "farming": "agriculture",
    "agribusiness": "agriculture",
    "edtech": "education",
    "renewable": "energy",
    "solar": "energy",
    "ict": "technology",
    "digital": "technology",
    "women": "gender",
    "girls": "gender",
}


def _normalize_focus(raw: list[str]) -> list[str]:
    out: list[str] = []
    for f in raw:
        key = f.strip().lower().replace(" ", "_")
        out.append(_FOCUS_SYNONYMS.get(key, key))
    # de-dupe, preserve order
    seen: set[str] = set()
    return [f for f in out if f and not (f in seen or seen.add(f))]


def researcher(ctx: Context, node_input) -> Event:
    """Normalize raw org input into an OrgProfile and write it to state.

    `node_input` is the user input parsed by START against the Workflow's
    input_schema (an OrgInput), or a dict if passed loosely.
    """
    # Accept either a parsed OrgInput, a dict, or (defensively) something with
    # the right attributes. Validate via the model so malformed input fails loud.
    if isinstance(node_input, OrgInput):
        raw = node_input
    elif isinstance(node_input, dict):
        raw = OrgInput.model_validate(node_input)
    else:
        raw = OrgInput.model_validate(getattr(node_input, "__dict__", {}) or {})

    # Scrub PII from any free-text fields before anything else touches them.
    safe_mission = pii_scrub(raw.mission or "")
    safe_free_text = pii_scrub(raw.free_text or "")

    profile = OrgProfile(
        name=raw.name,
        org_type=raw.org_type,
        country=raw.country.strip(),
        focus_areas=_normalize_focus(raw.focus_areas),
        mission=safe_mission,
        years_operating=raw.years_operating,
        registered=raw.registered,
        has_board=raw.has_board,
        has_audited_accounts=raw.has_audited_accounts,
        revenue_model=raw.revenue_model,
        budget_band=raw.budget_band,
        free_text=safe_free_text,
        preferred_grant_ids=raw.preferred_grant_ids,  # carry the human's selection through
    )

    # Optional, cosmetic LLM polish of the mission line. Decisions never depend on
    # this; if no key is configured `complete` returns None and we keep the input.
    polished = complete(
        "Rewrite this NGO/startup mission as one crisp sentence, no new facts:\n"
        f"{profile.mission}",
        system="You are a concise editor. Never invent facts.",
    )
    if polished:
        profile.mission = pii_scrub(polished)

    summary = (
        f"Profiled {profile.name} ({profile.org_type}, {profile.country}); "
        f"focus: {', '.join(profile.focus_areas) or 'unspecified'}."
    )
    # Persist via Event state delta (replay-safe) so downstream nodes read it.
    return Event(output=summary, state={"org_profile": profile.model_dump()})
