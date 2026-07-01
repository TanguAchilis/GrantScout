"""
Matching + ranking — pure Python, deliberately free of any ADK import so it can
be unit-tested in isolation and reused by the matcher node.

Two scores are computed SEPARATELY and never conflated (the spec is explicit):
  * fit_score          — mission/focus overlap, in [0, 1]. "Is this the kind of
                         work the funder cares about?"
  * eligibility_status — the deterministic verdict from eligibility.py. "Can this
                         org actually win it?"

WHY RANK ELIGIBILITY ABOVE FIT
------------------------------
A naive matcher sorts by fit and hands the org a beautiful grant it cannot win.
That is the flattery we refuse. So the ranking key is (eligibility_tier, -fit):
an *eligible* grant with mediocre fit outranks an *ineligible* grant with perfect
fit. The gaps travel with every match so the org sees exactly why something it
"looks perfect for" is ranked low — turning a disappointment into an action list.
"""
from __future__ import annotations

from grantscout.config import ELIGIBILITY_TIER_ORDER, MIN_FIT_TO_SURFACE
from grantscout.eligibility import check_eligibility
from grantscout.models import Grant, Match, OrgProfile


def compute_fit(profile: OrgProfile, grant: Grant) -> float:
    """Focus-area overlap as a Jaccard-ish ratio in [0, 1].

    Uses overlap / size-of-org-interests so an org whose every interest is covered
    scores 1.0 even if the grant also funds other areas. Falls back to 0.0 when
    the org declared no focus areas (we cannot claim a fit we can't measure)."""
    org_focus = {f.strip().lower() for f in profile.focus_areas if f.strip()}
    if not org_focus:
        return 0.0
    grant_focus = {f.strip().lower() for f in grant.focus_areas}
    overlap = org_focus & grant_focus
    return round(len(overlap) / len(org_focus), 3)


def build_match(profile: OrgProfile, grant: Grant) -> Match:
    """Score one grant: fit + deterministic eligibility, bundled with honest gaps."""
    fit = compute_fit(profile, grant)
    elig = check_eligibility(profile, grant)
    return Match(
        grant=grant,
        fit_score=fit,
        eligibility_status=elig["eligibility_status"],
        gaps=elig["gaps"],
        rationale="",  # filled in by the matcher node (LLM when available, else templated)
    )


def rank_matches(profile: OrgProfile, grants: list[Grant]) -> list[Match]:
    """Score and rank grants. Sort key = (eligibility_tier, -fit_score, title).

    Lower eligibility_tier is better (eligible=0, gaps=1, ineligible=2), so the
    sort places winnable grants first; within a tier, higher fit first; title is
    a stable tie-breaker. Grants below MIN_FIT_TO_SURFACE *and* ineligible are
    dropped entirely — no fit and no chance is just noise."""
    matches = [build_match(profile, g) for g in grants]

    def keep(m: Match) -> bool:
        if m.eligibility_status != "ineligible":
            return True  # winnable or fixable -> always worth showing
        return m.fit_score >= MIN_FIT_TO_SURFACE  # ineligible kept only if some fit

    kept = [m for m in matches if keep(m)]
    kept.sort(
        key=lambda m: (
            ELIGIBILITY_TIER_ORDER.get(m.eligibility_status, 99),
            -m.fit_score,
            m.grant.title,
        )
    )
    return kept


def select_grant_ids(
    ranked: list[Match], preferred: list[str] | None, max_selected: int = 2
) -> list[str]:
    """Decide which grants get drafted.

    * ``preferred is None`` -> auto-pick the top ``max_selected`` WINNABLE grants
      (eligible/gaps with some fit). Sensible default so the pipeline always has
      something concrete to draft.
    * ``preferred`` is a list -> honor the human's explicit choice: draft exactly
      those of the ranked grants. Any tier is allowed — a user may knowingly draft
      for an ineligible funder (the draft itself carries the caution). Order
      follows the ranking so display stays stable.
    """
    if preferred is None:
        return [
            m.grant.id
            for m in ranked
            if m.eligibility_status != "ineligible" and m.fit_score >= MIN_FIT_TO_SURFACE
        ][:max_selected]
    wanted = set(preferred)
    return [m.grant.id for m in ranked if m.grant.id in wanted]


__all__ = ["compute_fit", "build_match", "rank_matches", "select_grant_ids"]
