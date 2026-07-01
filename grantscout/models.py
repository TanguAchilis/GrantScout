"""
Typed data models shared across the MCP server, the eligibility/matching core,
and the graph nodes.

Design choice: the catalog stores `eligibility_requirements` as STRUCTURED
objects (a `code`, an optional `value`, and a human `label`), not as free-text
strings. The spec's `catalog` section shows example requirement *strings*
("2+ years operating", "audited accounts"); we deliberately encode them as
structured `EligibilityRequirement` records instead. That is what lets
eligibility.py make a DETERMINISTIC pass/fail decision in plain Python — the
whole honesty mechanism depends on requirements being machine-checkable rather
than prose the LLM has to interpret. Each record still carries a `label` for
display, so nothing human-readable is lost.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

OrgType = Literal["ngo_cbo", "startup_social_enterprise"]
EligibilityStatus = Literal["eligible", "gaps", "ineligible"]

# Requirement codes the deterministic checker understands. Adding a new hard
# requirement means: add a code here + a branch in eligibility.check_eligibility.
RequirementCode = Literal[
    "registered_entity",      # org must be a legally registered entity
    "min_years_operating",    # org must have operated >= `value` years
    "audited_accounts",       # org must have audited financial statements
    "functioning_board",      # org must have a functioning board
    "org_type",               # org_type must be in eligible_org_types (structural)
]


class EligibilityRequirement(BaseModel):
    """One machine-checkable funder requirement."""

    code: RequirementCode
    # Only meaningful for parameterized codes (e.g. min_years_operating -> 2).
    value: Optional[int] = None
    # Human-readable phrasing for display in matches/drafts.
    label: str


class Grant(BaseModel):
    """A funding opportunity. Mirrors the spec's `Grant` shape exactly."""

    id: str
    title: str
    funder: str
    focus_areas: list[str] = Field(default_factory=list)
    value_range: str
    deadline: str  # ISO date "YYYY-MM-DD" or "rolling"
    country_scope: list[str] = Field(default_factory=list)
    eligible_org_types: list[OrgType] = Field(default_factory=list)
    eligibility_requirements: list[EligibilityRequirement] = Field(default_factory=list)
    url: str
    source: str  # PUBLIC-source attribution (which roundup it came from)

    # --- Fields used by live discovery (discover_grants) only ---------------
    # Catalog entries leave these at their defaults. Discovered entries are
    # web-sourced and therefore UNTRUSTED: `description` holds the screened +
    # neutralized listing text, `discovered` marks provenance, and
    # `injection_flagged` records whether injection_screen tripped on it.
    description: Optional[str] = None
    discovered: bool = False
    injection_flagged: bool = False


class OrgInput(BaseModel):
    """
    Raw organization facts as provided by the user / local runner. This is what
    enters the graph. The researcher node normalizes it into an OrgProfile.

    Fields mirror exactly what funders screen on (the spec's researcher role),
    so the matcher can score eligibility against them.
    """

    name: str
    org_type: OrgType
    country: str
    focus_areas: list[str] = Field(default_factory=list)
    mission: str = ""
    years_operating: Optional[int] = None
    registered: Optional[bool] = None
    has_board: Optional[bool] = None
    has_audited_accounts: Optional[bool] = None
    revenue_model: Optional[str] = None  # for startups/social enterprises
    budget_band: Optional[str] = None
    # Optional extra narrative. In Phase 2 the LLM researcher can extract
    # structured fields from this; in Phase 1 it is carried through as context.
    free_text: str = ""

    # Human grant selection. None => let the matcher auto-pick the top winnable
    # grants to draft. A list => draft exactly those grant ids (the user chose
    # them in the UI). Empty list => the user chose none (draft nothing). Kept on
    # the input so selection flows through the SAME graph, not a side channel.
    preferred_grant_ids: Optional[list[str]] = None


class OrgProfile(OrgInput):
    """
    The normalized profile written to state.org_profile by the researcher.

    Inherits OrgInput's fields. `country` is lower-cased and focus_areas are
    normalized to the canonical vocabulary by the researcher node. Kept as a
    distinct type so downstream code is explicit about consuming the *normalized*
    profile, not the raw input.
    """


class Match(BaseModel):
    """One scored grant for the org. fit and eligibility are scored SEPARATELY."""

    grant: Grant
    fit_score: float  # mission/focus overlap in [0, 1]
    eligibility_status: EligibilityStatus
    gaps: list[str] = Field(default_factory=list)  # human-readable, honest gaps
    rationale: str = ""  # short explanation (LLM-written when available, else templated)


class Draft(BaseModel):
    """One drafted application section, grounded only in real profile data."""

    id: str
    grant_id: str
    section_type: str  # one of config.DRAFT_SECTION_TYPES
    title: str
    content: str  # may contain [ORG TO PROVIDE] markers for unknown facts


class ReviewDecision(BaseModel):
    """
    Human-in-the-loop response schema for the review gate (spec data_models).
    The person approves/edits/rejects drafts before anything is finalized.
    """

    approved_section_ids: list[str] = Field(default_factory=list)
    edits: dict[str, str] = Field(default_factory=dict)  # section_id -> replacement content
    rejected_ids: list[str] = Field(default_factory=list)
    note: str = ""
