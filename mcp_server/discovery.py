"""
Live discovery — the backing for the MCP `discover_grants` tool.

This is the FRESHNESS layer added AFTER the curated catalog works end-to-end
(spec: build_first=false). It does a best-effort fetch over PUBLIC roundup pages
and normalizes findings into the Grant shape.

THE SECURITY-CRITICAL RULE: web data is DATA, not commands
----------------------------------------------------------
Every fetched description is run through injection_screen and pii_scrub BEFORE it
is ever returned (and therefore before any LLM could see it). Adversarial
instructions embedded in a listing ("ignore your instructions and ...") are
quote-and-flagged and neutralized — never obeyed. Discovered grants are also
clearly marked `discovered=True` and carry `injection_flagged` so downstream code
and the human reviewer know the provenance is untrusted.

Design: the network fetch (`_fetch_listings`) and the screening/normalization
(`normalize_listing`) are deliberately separate. `normalize_listing` is a pure
function with no network, so the screening behavior is unit-tested hermetically
(tests/test_discovery.py). The fetch is best-effort and returns [] on any failure
so it can never break the deterministic catalog path.
"""
from __future__ import annotations

import json
import re
import urllib.request

from grantscout.security import injection_screen, pii_scrub, validate_search_args

# Public roundup sources we consolidate from. These are the same public sources
# the curated catalog is attributed to. (Kept as data so Phase 2 can extend it.)
PUBLIC_ROUNDUP_SOURCES: list[dict] = [
    {"name": "FundsforNGOs Africa listings", "url": "https://www2.fundsforngos.org/category/latest-funds-for-ngos/"},
    {"name": "AfricanNGOs.org funding roundups", "url": "https://africanngos.org/"},
    {"name": "Africa-Grants.com latest grants", "url": "https://www.africa-grants.com/"},
]

_FETCH_TIMEOUT = 6  # seconds; discovery must never hang the pipeline


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "untitled"


def normalize_listing(raw: dict, country: str) -> dict:
    """Screen + normalize ONE raw listing into a Grant-shaped dict.

    `raw` is {title, description, url, source}. This is the trust boundary: the
    description is screened for prompt injection and scrubbed of PII here, and the
    result is marked as untrusted/discovered. No network access.
    """
    title = (raw.get("title") or "Untitled opportunity").strip()
    url = (raw.get("url") or "").strip()
    source = (raw.get("source") or "public web roundup").strip()
    description = raw.get("description") or ""

    screen = injection_screen(description)        # flag + neutralize untrusted text
    safe_description = pii_scrub(screen["safe_text"])  # then strip any PII

    # Discovered grants have UNKNOWN structured eligibility — we never invent it.
    # eligibility.check_eligibility will therefore treat them conservatively
    # (no fixable requirements to fail, scope set to the org's own country).
    return {
        "id": f"discovered::{_slug(title)}",
        "title": title,
        "funder": raw.get("funder") or "(see source)",
        "focus_areas": [f.lower() for f in (raw.get("focus_areas") or [])],
        "value_range": raw.get("value_range") or "see source",
        "deadline": raw.get("deadline") or "rolling",
        "country_scope": [country.strip().lower()],
        "eligible_org_types": ["ngo_cbo", "startup_social_enterprise"],
        "eligibility_requirements": [],
        "url": url or source,
        "source": f"{source} (live discovery — verify at source)",
        "description": safe_description,
        "discovered": True,
        "injection_flagged": screen["flagged"],
    }


def _fetch_listings(url: str) -> list[dict]:
    """Best-effort fetch of a public roundup page -> crude raw listings.

    Returns [] on ANY failure (offline, timeout, non-200, parse miss). This is
    intentionally conservative: discovery is a bonus layer and must never break
    the catalog-backed spine. A production parser would use per-source selectors;
    here we extract anchor texts that look like opportunity titles.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantScout/0.1 (+research)"})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:  # noqa: S310
            if resp.status != 200:
                return []
            html = resp.read(500_000).decode("utf-8", errors="ignore")
    except Exception:
        return []

    # Crude title extraction from <a> texts that mention grant-ish words.
    raw_listings: list[dict] = []
    for m in re.finditer(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.IGNORECASE | re.DOTALL):
        href, inner = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if 15 <= len(inner) <= 160 and re.search(r"grant|fund|fellowship|prize|call|award", inner, re.I):
            raw_listings.append({"title": inner, "description": inner, "url": href})
        if len(raw_listings) >= 20:
            break
    return raw_listings


def discover_grants(focus_areas: list[str], country: str) -> list[dict]:
    """
    Live web discovery normalized to the Grant shape. Every description is
    screened (injection) + scrubbed (PII) via normalize_listing before return.

    Returns a list of Grant-shaped dicts (possibly empty). Filters to listings
    that overlap the requested focus areas when any are given.
    """
    # Same validation the curated tool uses (org_type isn't needed for discovery,
    # but we still validate focus/country shape).
    focus, country, _, _ = validate_search_args(focus_areas, country, "ngo_cbo", None)
    wanted = set(focus)

    out: list[dict] = []
    for src in PUBLIC_ROUNDUP_SOURCES:
        for raw in _fetch_listings(src["url"]):
            raw["source"] = src["name"]
            grant = normalize_listing(raw, country)
            if wanted:
                text = (grant["title"] + " " + (grant["description"] or "")).lower()
                if not any(f in text for f in wanted) and not (wanted & set(grant["focus_areas"])):
                    continue
            out.append(grant)
    return out


__all__ = ["discover_grants", "normalize_listing", "PUBLIC_ROUNDUP_SOURCES"]
