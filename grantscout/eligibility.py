"""
Eligibility scoring — the HONESTY MECHANISM, and the most important thing in the
whole project to get visibly right.

WHY THIS IS DETERMINISTIC PYTHON, NOT AN LLM PROMPT
---------------------------------------------------
Whether an organization meets a funder's hard requirements (registered? 2+ years
operating? audited accounts? functioning board? right org_type? right country?)
is a factual, checkable question. If we let an LLM "decide" pass/fail it can —
and language models reliably do — round generously: it will tell a hopeful NGO it
"looks eligible" because the framing rewards optimism. That is precisely the
failure mode this project exists to avoid. An org that wastes weeks writing a
proposal it can never win has been actively harmed by a flattering tool.

So the pass/fail decision lives here, in plain Python, where it is auditable,
testable, and incapable of being "talked into" a yes. The LLM's job downstream is
only to EXPLAIN the gaps in human terms — it never overrides this verdict.

OUTPUT
------
check_eligibility(profile, grant) -> {"eligibility_status": ..., "gaps": [...]}
  eligibility_status:
    "eligible"   — meets every hard requirement.
    "gaps"       — fails one or more FIXABLE requirements (years/audit/board/
                   registration). "Not yet eligible" — a feature, not a failure:
                   the org now knows exactly what to build toward.
    "ineligible" — fails a STRUCTURAL requirement (wrong org_type or out of the
                   funder's country scope). These are not things the org can
                   quickly "fix", so we say so plainly and the matcher ranks the
                   grant lowest rather than dangling false hope.
"""
from __future__ import annotations

from grantscout.config import CONTINENT_WILDCARDS
from grantscout.models import EligibilityStatus, Grant, OrgProfile
from mcp_server.catalog_search import _country_in_scope


def check_eligibility(profile: OrgProfile, grant: Grant) -> dict:
    """Run every hard requirement for one grant against one org profile.

    Returns a dict (JSON-serializable) so it drops straight into Match objects
    and traces. `gaps` is human-readable on purpose — it is the honest message
    the org actually needs to read.
    """
    gaps: list[str] = []
    structural_fail = False

    # --- Structural requirement 1: org_type must be an eligible audience -------
    # org_type rides through the pipeline as data; here is where it actually
    # matters. A health NGO simply is not who a startup accelerator funds, no
    # matter how strong the mission fit looks.
    if profile.org_type not in grant.eligible_org_types:
        gaps.append(
            f"This funder supports {_join(grant.eligible_org_types)}; "
            f"your organization is registered as '{profile.org_type}'."
        )
        structural_fail = True

    # --- Structural requirement 2: country must be in the funder's scope -------
    if not _country_in_scope(profile.country, grant.country_scope):
        gaps.append(
            f"This funder's geographic scope is {_join(grant.country_scope)}; "
            f"'{profile.country}' is outside it."
        )
        structural_fail = True

    # --- Fixable requirements (drive 'gaps' status, not 'ineligible') ---------
    # Each branch is intentionally explicit so the gap message names the exact
    # bar and the org's current standing. We treat "unknown" (None) as NOT met:
    # we never assume in the org's favour — that would be the same dishonesty as
    # an LLM rounding up.
    for req in grant.eligibility_requirements:
        if req.code == "org_type":
            # Structural; already handled above (the catalog uses this code as a
            # human-readable note about the target audience). Skip to avoid a
            # duplicate gap line.
            continue

        if req.code == "min_years_operating":
            minimum = req.value or 0
            years = profile.years_operating
            if years is None:
                gaps.append(
                    f"Requires {minimum}+ years operating; your years_operating "
                    f"is not stated [ORG TO CONFIRM]."
                )
            elif years < minimum:
                gaps.append(
                    f"Requires {minimum}+ years operating; you reported {years}."
                )

        elif req.code == "audited_accounts":
            if profile.has_audited_accounts is not True:
                gaps.append("Requires audited accounts; you do not report having them.")

        elif req.code == "functioning_board":
            if profile.has_board is not True:
                gaps.append("Requires a functioning board; you do not report having one.")

        elif req.code == "registered_entity":
            if profile.registered is not True:
                gaps.append("Requires a legally registered entity; you do not report being registered.")

    status: EligibilityStatus
    if structural_fail:
        # A structural failure dominates: even if every fixable box were ticked,
        # the org is not who/where this funder funds. Never silently upgrade.
        status = "ineligible"
    elif gaps:
        status = "gaps"
    else:
        status = "eligible"

    return {"eligibility_status": status, "gaps": gaps}


def _join(items: list[str]) -> str:
    """Human-friendly comma join: ['a','b'] -> 'a or b'."""
    pretty = [i.replace("_", " ") for i in items]
    if len(pretty) <= 1:
        return pretty[0] if pretty else "(unspecified)"
    return ", ".join(pretty[:-1]) + f" or {pretty[-1]}"


__all__ = ["check_eligibility", "CONTINENT_WILDCARDS"]
