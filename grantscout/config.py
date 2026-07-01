"""
Central configuration: model name, scoring thresholds, canonical vocabularies,
and defaults. NO SECRETS live here — keys come from environment variables only
(see security.py / .env.example).

Keeping these constants in one place means the eligibility/matching logic and the
nodes share a single source of truth, and Phase 2 can tweak thresholds without
touching node code.
"""
from __future__ import annotations

import os

# -- Model ------------------------------------------------------------------
# gemini-flash-latest per the spec. Overridable via env so Phase 2 can point at
# a pinned model without code changes. This is just a STRING; no key is read here.
MODEL: str = os.environ.get("GRANTSCOUT_MODEL", "gemini-flash-latest")

# -- Org-type vocabulary ----------------------------------------------------
# org_type is a profile FIELD that drives eligibility scoring, NOT a graph branch.
# Both audiences flow through the same pipeline.
ORG_TYPES: frozenset[str] = frozenset({"ngo_cbo", "startup_social_enterprise"})

# -- Focus-area vocabulary (canonical; free-text is normalized against this) --
FOCUS_AREAS: frozenset[str] = frozenset(
    {
        "health",
        "education",
        "agriculture",
        "climate",
        "environment",
        "water_sanitation",
        "gender",
        "youth",
        "livelihoods",
        "financial_inclusion",
        "technology",
        "human_rights",
        "governance",
        "energy",
        "food_security",
        "entrepreneurship",
        "arts_culture",
    }
)

# -- Country-scope wildcards ------------------------------------------------
# Many African grants are "pan-African" rather than single-country. A grant whose
# country_scope contains any of these matches an org in ANY African country.
CONTINENT_WILDCARDS: frozenset[str] = frozenset(
    {"africa", "pan-african", "pan_african", "sub-saharan africa", "all_africa", "continental"}
)

# -- Scoring thresholds -----------------------------------------------------
# fit_score is focus-area overlap in [0, 1]. A grant must clear this to be worth
# surfacing as a "fit" at all (it can still appear lower with gaps/ineligible).
MIN_FIT_TO_SURFACE: float = 0.01

# Ranking tier order: eligible matches outrank "gaps" outrank "ineligible".
# This is the honesty lever — a high-FIT but INELIGIBLE grant is intentionally
# ranked BELOW a lower-fit grant the org can actually win, so we never flatter
# the org into wasting effort on something it cannot get.
ELIGIBILITY_TIER_ORDER: dict[str, int] = {
    "eligible": 0,
    "gaps": 1,
    "ineligible": 2,
}

# -- Draft section types the drafter produces (exactly two, per spec) --------
DRAFT_SECTION_TYPES: tuple[str, str] = ("problem_statement", "funder_alignment")

# -- Catalog location -------------------------------------------------------
import pathlib

CATALOG_PATH = pathlib.Path(__file__).resolve().parent.parent / "mcp_server" / "catalog.json"
