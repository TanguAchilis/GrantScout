"""
Catalog search — the deterministic core behind the MCP `search_grants` tool.

Design choice: the actual filtering/loading logic lives HERE, not inside the MCP
server's tool wrapper. That way exactly one implementation backs both:
  * mcp_server/server.py            -> exposes it over MCP (stdio)
  * grantscout/nodes/matcher.py     -> calls it directly in-process

The matcher calling the shared function in-process (rather than spinning up an
MCP client subprocess) keeps the local Phase-1 demo runnable offline with zero
moving parts, while the MCP server still genuinely exposes the identical tool.
The contract (inputs/outputs) is the same either way.
"""
from __future__ import annotations

import json
from functools import lru_cache

from grantscout.config import CATALOG_PATH, CONTINENT_WILDCARDS
from grantscout.models import Grant


@lru_cache(maxsize=1)
def load_catalog() -> list[Grant]:
    """Load + validate the curated catalog once (cached). Validates every entry
    against the Grant schema so a malformed catalog fails loudly at load time."""
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [Grant.model_validate(g) for g in raw["grants"]]


# Minimal country -> region map so single-country orgs match regional-scope grants.
_REGION_MEMBERS = {
    "east africa": {"kenya", "tanzania", "uganda", "rwanda", "ethiopia", "burundi", "south sudan", "somalia"},
    "west africa": {"nigeria", "ghana", "senegal", "cote d'ivoire", "côte d'ivoire", "mali", "benin", "togo", "sierra leone", "liberia", "burkina faso", "guinea"},
    "southern africa": {"south africa", "zambia", "zimbabwe", "malawi", "mozambique", "botswana", "namibia", "lesotho", "eswatini"},
    "central africa": {"cameroon", "drc", "democratic republic of congo", "congo", "gabon", "chad", "central african republic"},
    "north africa": {"egypt", "morocco", "tunisia", "algeria", "libya", "sudan"},
}


def _country_in_scope(country: str, scope: list[str]) -> bool:
    """A country matches a grant's scope if the scope is a continent-wide wildcard
    (e.g. 'africa'), names the country exactly, or names a region the country
    belongs to (e.g. an org in Kenya matches 'east africa').

    Country scope only governs whether a grant is even *shown*. It is NOT the
    eligibility decision — eligibility.py makes the honest qualify/not-qualify
    call separately. An empty scope is treated as continent-wide.
    """
    if not scope:
        return True
    c = country.strip().lower()
    for s in scope:
        s = s.strip().lower()
        if s in CONTINENT_WILDCARDS:
            return True
        if c == s:
            return True
        members = _REGION_MEMBERS.get(s)
        if members and c in members:
            return True
    return False


def _deadline_ok(deadline: str, max_deadline: str | None) -> bool:
    """Keep grants whose deadline is on/before max_deadline. Non-dated cycles
    ('rolling'/'annual') always pass — there is no fixed cutoff to compare."""
    if not max_deadline:
        return True
    d = deadline.strip().lower()
    if d in {"rolling", "annual"}:
        return True
    # ISO date string comparison is lexicographically correct for YYYY-MM-DD.
    return deadline <= max_deadline


def search_grants(
    focus_areas: list[str],
    country: str,
    org_type: str,
    max_deadline: str | None = None,
) -> list[dict]:
    """
    Filter the curated catalog. Returns grants as plain dicts (JSON-serializable,
    so the same return shape works over MCP and in-process).

    A grant is returned when:
      * org_type is in the grant's eligible_org_types  (pre-filter — eligibility.py
        still runs the full honest check later, but there is no point surfacing a
        grant for the wrong audience), AND
      * the org's country falls within the grant's country_scope, AND
      * at least one focus area overlaps (if focus_areas given), AND
      * the deadline is on/before max_deadline (if given).

    Note: input validation/type-checking is enforced at the MCP boundary
    (security.validate_search_args); this function assumes already-validated args.
    """
    wanted = {f.strip().lower() for f in focus_areas if f and f.strip()}
    results: list[dict] = []
    for g in load_catalog():
        if org_type not in g.eligible_org_types:
            continue
        if not _country_in_scope(country, g.country_scope):
            continue
        if wanted:
            grant_focus = {f.lower() for f in g.focus_areas}
            if not (wanted & grant_focus):
                continue
        if not _deadline_ok(g.deadline, max_deadline):
            continue
        results.append(g.model_dump())
    return results
