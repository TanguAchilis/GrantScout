"""
Matcher ranking tests. The headline guarantee: an ELIGIBLE grant with weaker
focus fit must rank ABOVE an INELIGIBLE grant with perfect fit. We refuse to
flatter the org with grants it cannot win.
"""
from __future__ import annotations

from grantscout.matching import compute_fit, rank_matches, select_grant_ids

from .conftest import make_grant, make_profile


def test_compute_fit_overlap():
    org = make_profile(focus_areas=["health", "education"])
    g = make_grant(focus_areas=["health", "climate"])
    # 1 of the org's 2 interests covered -> 0.5
    assert compute_fit(org, g) == 0.5


def test_compute_fit_zero_when_org_has_no_focus():
    org = make_profile(focus_areas=[])
    assert compute_fit(org, make_grant()) == 0.0


def test_eligible_outranks_higher_fit_but_ineligible():
    org = make_profile(focus_areas=["health"], org_type="ngo_cbo")

    # Perfect-fit grant the org is INELIGIBLE for (wrong audience).
    perfect_but_wrong = make_grant(
        id="perfect-wrong",
        title="Perfect Fit Startup Fund",
        focus_areas=["health"],
        eligible_org_types=["startup_social_enterprise"],
        eligibility_requirements=[],
    )
    # Weaker-fit grant the org IS eligible for.
    winnable = make_grant(
        id="winnable",
        title="Winnable Health Grant",
        focus_areas=["health", "education", "climate"],  # fit < 1.0
        eligible_org_types=["ngo_cbo"],
        eligibility_requirements=[],
        country_scope=["africa"],
    )

    ranked = rank_matches(org, [perfect_but_wrong, winnable])
    assert ranked[0].grant.id == "winnable"
    assert ranked[0].eligibility_status == "eligible"
    # The perfect-fit-but-ineligible grant is ranked BELOW, with its gap shown.
    assert ranked[-1].grant.id == "perfect-wrong"
    assert ranked[-1].eligibility_status == "ineligible"
    assert ranked[-1].gaps  # honest reason travels with the match


def test_select_grant_ids_auto_vs_explicit():
    org = make_profile(focus_areas=["health"])
    a = make_grant(id="a", title="A", eligibility_requirements=[], country_scope=["africa"])
    b = make_grant(id="b", title="B", eligibility_requirements=[], country_scope=["africa"])
    c = make_grant(id="c", title="C", eligibility_requirements=[], country_scope=["africa"])
    ranked = rank_matches(org, [a, b, c])

    # None -> auto-pick the top `max_selected` winnable grants.
    assert select_grant_ids(ranked, None, max_selected=2) == ["a", "b"]
    # Explicit list -> exactly those (ranking order preserved).
    assert select_grant_ids(ranked, ["c", "a"], max_selected=2) == ["a", "c"]
    # Empty list -> the human chose none.
    assert select_grant_ids(ranked, [], max_selected=2) == []
    # Unknown ids are ignored.
    assert select_grant_ids(ranked, ["nope"], max_selected=2) == []


def test_gaps_rank_between_eligible_and_ineligible():
    org = make_profile(focus_areas=["health"], has_audited_accounts=False, years_operating=1)
    eligible = make_grant(id="elig", title="A Eligible", eligibility_requirements=[], country_scope=["africa"])
    gappy = make_grant(id="gappy", title="B Gappy", country_scope=["africa"])  # needs audit + years
    ineligible = make_grant(
        id="inelig", title="C Ineligible", eligible_org_types=["startup_social_enterprise"], eligibility_requirements=[]
    )
    ranked = rank_matches(org, [gappy, ineligible, eligible])
    statuses = [m.eligibility_status for m in ranked]
    assert statuses == ["eligible", "gaps", "ineligible"]
