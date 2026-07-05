"""
Matcher node.

Role (per spec): call the MCP search_grants tool (and optionally discover_grants)
with the org's focus/country/org_type; for each grant score mission/focus FIT and
ELIGIBILITY *separately*; surface eligibility GAPS explicitly; never inflate
readiness — a grant the org fails a hard requirement for is ranked LOWER, with
the reason shown.

HOW THE HONESTY IS ENFORCED HERE
--------------------------------
This node does NOT ask the LLM whether the org qualifies. It calls the
deterministic ranker (matching.rank_matches -> eligibility.check_eligibility),
which sorts winnable grants above merely-high-fit ones and attaches the concrete
gaps. The LLM is used at most to phrase a one-line rationale; it can never
override the verdict or hide a gap.

MCP boundary: search_grants is the curated-catalog tool. We call its shared
implementation in-process (see mcp_server/catalog_search.py for why), validating
the args through security.validate_search_args exactly as the MCP server does.
discover_grants (live web) is an OPTIONAL second source, off by default so the
local Phase-1 run is hermetic; enable it with GRANTSCOUT_ENABLE_DISCOVERY=1.
"""
from __future__ import annotations

import os

from google.adk.agents.context import Context
from google.adk.events.event import Event

from grantscout.llm import complete
from grantscout.matching import rank_matches, select_grant_ids
from grantscout.models import Grant, Match, OrgProfile
from grantscout.security import validate_search_args
from mcp_server.catalog_search import search_grants

# How many winnable (eligible/gaps) grants to pre-select for drafting. The human
# can change this at the review gate; this is just a sensible default so the
# offline pipeline has something concrete to draft.
_MAX_SELECTED = 2


def _gather_grants(profile: OrgProfile) -> list[Grant]:
    """Query the curated catalog (always) and live discovery (optional)."""
    focus, country, org_type, _ = validate_search_args(
        profile.focus_areas, profile.country, profile.org_type, None
    )
    rows = search_grants(focus_areas=focus, country=country, org_type=org_type)

    if os.environ.get("GRANTSCOUT_ENABLE_DISCOVERY", "").strip() in {"1", "true", "TRUE"}:
        # Imported lazily so the offline path never imports networking code.
        from mcp_server.discovery import discover_grants

        rows += discover_grants(focus_areas=focus, country=country)

    # De-duplicate by id (discovery may echo a catalog entry).
    by_id: dict[str, dict] = {}
    for r in rows:
        by_id.setdefault(r["id"], r)
    return [Grant.model_validate(r) for r in by_id.values()]


def _base_rationale(match: Match) -> str:
    """Deterministic, always-honest one-liner (fit + eligibility + gaps)."""
    return (
        f"Grant '{match.grant.title}' by {match.grant.funder}. "
        f"Focus fit {match.fit_score:.0%}. Eligibility: {match.eligibility_status}. "
        f"Gaps: {'; '.join(match.gaps) if match.gaps else 'none'}."
    )


def _rationale(match: Match) -> str:
    """LLM-phrased honest summary, falling back to the deterministic base."""
    base = _base_rationale(match)
    polished = complete(
        "In ONE sentence, neutrally summarize this match for the applicant. Do "
        "not overstate readiness; if there are gaps, mention them honestly:\n"
        f"{base}",
        system="You are an honest grants advisor. Never flatter; never hide gaps.",
    )
    return polished or base


def matcher(ctx: Context) -> Event:
    """Score + rank grants for the profiled org; write ranked matches to state."""
    data = ctx.state.get("org_profile")
    if not data:
        # Upstream contract violated; raise so ADK surfaces it (do NOT swallow).
        raise ValueError("matcher: state.org_profile missing (researcher must run first)")
    profile = OrgProfile.model_validate(data)

    grants = _gather_grants(profile)
    ranked = rank_matches(profile, grants)

    # Which grants to draft: honor the human's explicit choice if provided
    # (profile.preferred_grant_ids), else auto-pick the top winnable grants.
    selected = select_grant_ids(ranked, profile.preferred_grant_ids, _MAX_SELECTED)
    selected_set = set(selected)

    # Cost/quota: only spend an LLM call to phrase a rationale for the grants we
    # are actually drafting; every other match gets the deterministic (still
    # honest) one-liner. This cuts a typical run from ~one-call-per-grant to a
    # couple of calls, and the eligibility verdict is unaffected either way.
    for m in ranked:
        m.rationale = _rationale(m) if m.grant.id in selected_set else _base_rationale(m)

    n_elig = sum(1 for m in ranked if m.eligibility_status == "eligible")
    n_gaps = sum(1 for m in ranked if m.eligibility_status == "gaps")
    summary = (
        f"Matched {len(ranked)} grants: {n_elig} eligible, {n_gaps} with gaps. "
        f"Selected {len(selected)} for drafting."
    )
    return Event(
        output=summary,
        state={
            "matches": [m.model_dump() for m in ranked],
            "selected_grant_ids": selected,
        },
    )
