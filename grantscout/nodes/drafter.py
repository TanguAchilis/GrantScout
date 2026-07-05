"""
Drafter node.

Role (per spec): for the selected grant(s), draft EXACTLY TWO section types,
grounded ONLY in the org's real profile data (no fabricated facts):
  (1) problem/need statement
  (2) funder-alignment section mapping the org's work to THAT funder's priorities.
Keep it specific and honest; mark anything the org must fill in with real numbers
as [ORG TO PROVIDE].

WHY GROUNDED-ONLY MATTERS
-------------------------
A grant draft that invents beneficiary counts or budget figures is worse than
useless — it can sink an application and the org's credibility. So the drafter
only ever states facts present in the profile; every quantitative or specific
claim the profile does not contain becomes an explicit [ORG TO PROVIDE] marker.
When the LLM is available it phrases the prose, but it is instructed not to add
facts; the deterministic fallback guarantees the same grounding offline.
"""
from __future__ import annotations

import json
import re

from google.adk.agents.context import Context
from google.adk.events.event import Event

from grantscout.config import DRAFT_SECTION_TYPES
from grantscout.llm import complete
from grantscout.models import Draft, Grant, Match, OrgProfile

# Marker the org must replace with a real figure/specific. Centralized so the
# README and the review UI can grep for it.
PROVIDE = "[ORG TO PROVIDE]"


def _problem_statement(profile: OrgProfile, grant: Grant) -> str:
    focus = ", ".join(profile.focus_areas) or PROVIDE
    mission = profile.mission or PROVIDE
    return (
        f"## Problem / Need Statement\n\n"
        f"{profile.name} works in {profile.country} on {focus}. "
        f"{mission}\n\n"
        f"In the communities we serve, the core problem is {PROVIDE} "
        f"(describe the specific need, who is affected, and scale — e.g. number of "
        f"people, region). Current provision is inadequate because {PROVIDE}. "
        f"Without intervention, {PROVIDE} (state the consequence). "
        f"Our work directly addresses this gap by {PROVIDE} "
        f"(summarize your approach in 1-2 sentences)."
    )


def _funder_alignment(profile: OrgProfile, match: Match) -> str:
    grant = match.grant
    shared = sorted(set(f.lower() for f in profile.focus_areas) & set(f.lower() for f in grant.focus_areas))
    shared_str = ", ".join(shared) if shared else PROVIDE
    # Honesty: if there are eligibility gaps, the alignment section states them
    # plainly rather than papering over them.
    if match.eligibility_status == "eligible":
        honesty = "Our organization meets this funder's stated eligibility requirements."
    elif match.eligibility_status == "gaps":
        honesty = (
            "Note — before/within this application we must address: "
            + "; ".join(match.gaps)
            + "."
        )
    else:
        honesty = (
            "Caution — this funder appears to be a structural mismatch: "
            + "; ".join(match.gaps)
            + ". Consider whether to apply."
        )
    return (
        f"## Alignment with {grant.funder}\n\n"
        f"{grant.funder}'s {grant.title} prioritizes {', '.join(grant.focus_areas)}. "
        f"{profile.name}'s work in {shared_str} maps directly to these priorities. "
        f"Specifically, our programming on {shared_str} advances the funder's goals by {PROVIDE} "
        f"(give 1-2 concrete examples of activities and outcomes). "
        f"Our intended use of the {grant.value_range} award is {PROVIDE} "
        f"(outline the budget at a high level).\n\n"
        f"{honesty}"
    )


def _polish_pair(problem: str, alignment: str) -> tuple[str, str]:
    """Polish BOTH sections of a grant in ONE LLM call (half the calls vs. one per
    section). Returns (problem, alignment). Falls back to the deterministic input
    for either section if the LLM is unavailable, the JSON is malformed, or a
    marker was dropped — grounding is never sacrificed for prose.
    """
    prompt = (
        "Improve the writing flow of these two grant sections. Do NOT add any "
        "facts, numbers, or claims not already present. PRESERVE every "
        "'[ORG TO PROVIDE]' marker exactly. Return ONLY compact JSON of the form "
        '{"problem": "...", "alignment": "..."} with no other text.\n\n'
        f"PROBLEM:\n{problem}\n\nALIGNMENT:\n{alignment}"
    )
    raw = complete(
        prompt,
        system="You are an honest grant-writing assistant. Never invent facts. Output JSON only.",
    )
    if not raw:
        return problem, alignment
    match = re.search(r"\{.*\}", raw, re.DOTALL)  # tolerate code fences / stray text
    if not match:
        return problem, alignment
    try:
        data = json.loads(match.group(0))
        p, a = data.get("problem"), data.get("alignment")
    except (ValueError, TypeError):
        return problem, alignment
    # Keep a polished section only if it's a string AND preserves its markers.
    p_ok = isinstance(p, str) and p.count(PROVIDE) >= problem.count(PROVIDE)
    a_ok = isinstance(a, str) and a.count(PROVIDE) >= alignment.count(PROVIDE)
    return (p if p_ok else problem, a if a_ok else alignment)


def drafter(ctx: Context) -> Event:
    """Draft the two section types for each selected grant; write to state.drafts."""
    profile = OrgProfile.model_validate(ctx.state.get("org_profile") or {})
    matches = [Match.model_validate(m) for m in (ctx.state.get("matches") or [])]
    selected_ids = ctx.state.get("selected_grant_ids") or []
    by_id = {m.grant.id: m for m in matches}

    drafts: list[Draft] = []
    for gid in selected_ids:
        match = by_id.get(gid)
        if not match:
            continue
        grant = match.grant
        problem, alignment = _polish_pair(
            _problem_statement(profile, grant), _funder_alignment(profile, match)
        )
        drafts.append(
            Draft(
                id=f"{gid}::{DRAFT_SECTION_TYPES[0]}",
                grant_id=gid,
                section_type=DRAFT_SECTION_TYPES[0],
                title=f"Problem Statement — {grant.title}",
                content=problem,
            )
        )
        drafts.append(
            Draft(
                id=f"{gid}::{DRAFT_SECTION_TYPES[1]}",
                grant_id=gid,
                section_type=DRAFT_SECTION_TYPES[1],
                title=f"Funder Alignment — {grant.title}",
                content=alignment,
            )
        )

    summary = f"Drafted {len(drafts)} sections across {len(selected_ids)} grant(s)."
    return Event(output=summary, state={"drafts": [d.model_dump() for d in drafts]})
