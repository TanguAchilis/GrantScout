"""
Eligibility tests — the honesty mechanism. The most important test here is
`test_looks_like_a_fit_but_fails_hard_requirement`: an org that matches focus,
org_type, and country perfectly but lacks a hard requirement must NOT be reported
eligible. That is the exact dishonesty the deterministic checker exists to block.
"""
from __future__ import annotations

from grantscout.eligibility import check_eligibility

from .conftest import make_grant, make_profile


def test_fully_qualified_org_is_eligible(profile, grant):
    result = check_eligibility(profile, grant)
    assert result["eligibility_status"] == "eligible"
    assert result["gaps"] == []


def test_looks_like_a_fit_but_fails_hard_requirement(grant):
    # Perfect focus/org_type/country fit, but NO audited accounts and only 1 year.
    org = make_profile(years_operating=1, has_audited_accounts=False)
    result = check_eligibility(org, grant)

    # Crucially: NOT silently upgraded to eligible.
    assert result["eligibility_status"] == "gaps"
    # Both unmet hard requirements are surfaced honestly.
    joined = " ".join(result["gaps"]).lower()
    assert "audited accounts" in joined
    assert "2+ years" in joined or "2 + years" in joined or "years operating" in joined


def test_org_type_mismatch_is_ineligible(grant):
    # A startup applying to an NGO-only fund: strong focus fit, wrong audience.
    org = make_profile(org_type="startup_social_enterprise")
    result = check_eligibility(org, grant)
    assert result["eligibility_status"] == "ineligible"
    assert any("registered as 'startup_social_enterprise'" in g for g in result["gaps"])


def test_country_out_of_scope_is_ineligible(grant):
    org = make_profile(country="Morocco")  # north africa, grant is east africa
    result = check_eligibility(org, grant)
    assert result["eligibility_status"] == "ineligible"
    assert any("outside it" in g for g in result["gaps"])


def test_unknown_facts_count_against_not_for_the_org(grant):
    # years_operating / audited / board unknown (None) -> treated as NOT met.
    # We never assume in the org's favour (same dishonesty as an LLM rounding up).
    org = make_profile(years_operating=None, has_audited_accounts=None, has_board=None, registered=None)
    result = check_eligibility(org, grant)
    assert result["eligibility_status"] == "gaps"
    assert len(result["gaps"]) == 4  # all four fixable requirements flagged


def test_no_requirements_means_eligible_when_structural_ok():
    org = make_profile(org_type="startup_social_enterprise", registered=None, years_operating=None)
    g = make_grant(
        eligible_org_types=["startup_social_enterprise"],
        eligibility_requirements=[],  # an open early-stage prize
        country_scope=["africa"],
    )
    result = check_eligibility(org, g)
    assert result["eligibility_status"] == "eligible"
    assert result["gaps"] == []


def test_continent_wildcard_scope_matches_any_african_country(grant):
    org = make_profile(country="Nigeria")
    g = make_grant(country_scope=["africa"])
    result = check_eligibility(org, g)
    # Nigeria is in 'africa' wildcard, so country is NOT the blocker here.
    assert not any("outside it" in gap for gap in result["gaps"])
