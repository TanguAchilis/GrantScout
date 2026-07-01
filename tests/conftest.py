"""Shared fixtures: small, explicit Grant/OrgProfile builders for the core tests."""
from __future__ import annotations

import pytest

from grantscout.models import EligibilityRequirement, Grant, OrgProfile


def make_grant(**overrides) -> Grant:
    """A health-NGO grant requiring registration, 2 years, audit, and a board."""
    base = dict(
        id="test-grant",
        title="Test Health Fund",
        funder="Test Funder",
        focus_areas=["health", "water_sanitation"],
        value_range="$10,000–$50,000",
        deadline="rolling",
        country_scope=["east africa"],
        eligible_org_types=["ngo_cbo"],
        eligibility_requirements=[
            EligibilityRequirement(code="registered_entity", label="Registered"),
            EligibilityRequirement(code="min_years_operating", value=2, label="2+ years"),
            EligibilityRequirement(code="audited_accounts", label="Audited accounts"),
            EligibilityRequirement(code="functioning_board", label="Board"),
        ],
        url="https://example.org/grant",
        source="Test public roundup",
    )
    base.update(overrides)
    return Grant(**base)


def make_profile(**overrides) -> OrgProfile:
    """A fully-qualified Kenyan health NGO (meets every requirement by default)."""
    base = dict(
        name="Test CBO",
        org_type="ngo_cbo",
        country="Kenya",
        focus_areas=["health", "water_sanitation"],
        mission="Improve community health.",
        years_operating=5,
        registered=True,
        has_board=True,
        has_audited_accounts=True,
    )
    base.update(overrides)
    return OrgProfile(**base)


@pytest.fixture
def grant():
    return make_grant()


@pytest.fixture
def profile():
    return make_profile()
