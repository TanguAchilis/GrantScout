"""
GrantScout MCP server — the "filing cabinet" with two drawers.

Tools exposed over stdio (python-mcp-sdk / FastMCP):
  * search_grants   — query the curated catalog.json (the reliable core).
  * discover_grants — live web discovery over public roundups (the freshness
                      layer; web text is screened for prompt injection).

Run it standalone:
    python -m mcp_server.server          # speaks MCP over stdio

WHY THE TOOL BODIES ARE THIN
----------------------------
The real logic lives in catalog_search.py and discovery.py so that the EXACT
same implementations back both this MCP server and the in-process matcher node.
Here we only (1) validate + type-check inputs (rejecting malformed payloads — a
security requirement) and (2) delegate. Least privilege: this server only reads
the catalog and fetches public pages; it holds no secrets and writes nothing.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from grantscout.security import validate_search_args
from mcp_server.catalog_search import search_grants as _search_grants
from mcp_server.discovery import discover_grants as _discover_grants

mcp = FastMCP("grantscout")


@mcp.tool(
    description=(
        "Search the curated catalog of African funding opportunities. Filters by "
        "focus areas, country, and org_type ('ngo_cbo' or 'startup_social_enterprise'); "
        "optional max_deadline (YYYY-MM-DD). Returns grants with eligible_org_types and "
        "structured eligibility_requirements so callers can score eligibility honestly."
    )
)
def search_grants(
    focus_areas: list[str],
    country: str,
    org_type: str,
    max_deadline: str | None = None,
) -> list[dict]:
    # Validate at the boundary; raises ValueError on malformed input.
    focus, country, org_type, max_deadline = validate_search_args(
        focus_areas, country, org_type, max_deadline
    )
    return _search_grants(focus, country, org_type, max_deadline)


@mcp.tool(
    description=(
        "Live discovery of African funding opportunities from PUBLIC roundup pages, "
        "normalized to the same Grant shape. Every fetched description is screened for "
        "prompt injection and scrubbed of PII before return; results are marked as "
        "untrusted (discovered=True). Use as a freshness layer on top of search_grants."
    )
)
def discover_grants(focus_areas: list[str], country: str) -> list[dict]:
    # org_type isn't a discovery filter, but we reuse the same validator shape.
    focus, country, _, _ = validate_search_args(focus_areas, country, "ngo_cbo", None)
    return _discover_grants(focus, country)


def main() -> None:
    """Entry point: serve the two tools over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
