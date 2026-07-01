"""
Catalog + search_grants tests: the catalog meets the spec's bar (>=25 attributed
entries, all valid) and the filter behaves (org_type / focus / country).
"""
from __future__ import annotations

from mcp_server.catalog_search import load_catalog, search_grants


def test_catalog_has_at_least_25_entries():
    catalog = load_catalog()
    assert len(catalog) >= 25


def test_every_entry_is_attributed_and_well_formed():
    for g in load_catalog():
        assert g.source.strip(), f"{g.id} missing source attribution"
        assert g.url.startswith("http"), f"{g.id} missing url"
        assert g.eligible_org_types, f"{g.id} missing eligible_org_types"
        assert g.focus_areas, f"{g.id} missing focus_areas"


def test_search_filters_by_org_type():
    results = search_grants(focus_areas=[], country="Kenya", org_type="ngo_cbo")
    assert results, "expected some NGO grants for Kenya"
    assert all("ngo_cbo" in r["eligible_org_types"] for r in results)


def test_search_filters_by_focus_area():
    results = search_grants(focus_areas=["gender"], country="Nigeria", org_type="ngo_cbo")
    assert results
    assert all(any(f in r["focus_areas"] for f in ["gender"]) for r in results)


def test_search_respects_country_scope():
    # Acumen is West/East Africa only; an org in Morocco (north africa) shouldn't match it.
    results = search_grants(focus_areas=["livelihoods"], country="Morocco", org_type="startup_social_enterprise")
    assert all(r["id"] != "acumen-fellowship" for r in results)


def test_search_returns_json_serializable_dicts():
    import json

    results = search_grants(focus_areas=["health"], country="Kenya", org_type="ngo_cbo")
    json.dumps(results)  # must not raise
