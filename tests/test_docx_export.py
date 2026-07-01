"""
Word export test: build_docx produces a valid .docx (openable by python-docx)
that contains the org name, grant/section headings, body text, and the
[ORG TO PROVIDE] markers. Hermetic — no server, no network.
"""
from __future__ import annotations

import io

import pytest

# Skip cleanly if the optional `web` extra (python-docx) isn't installed.
docx = pytest.importorskip("docx")

from web.docx_export import build_docx  # noqa: E402


def _sample_groups():
    return [
        {
            "grant_title": "African Women's Development Fund (AWDF) Grants",
            "sections": [
                {"title": "Problem Statement — AWDF", "content": "## Problem / Need Statement\n\nWe serve rural Kenya. The core problem is [ORG TO PROVIDE]."},
                {"title": "Funder Alignment — AWDF", "content": "## Alignment\n\nOur work maps to the funder's priorities."},
            ],
        }
    ]


def test_build_docx_returns_openable_document():
    data = build_docx("Maji Bora Community Initiative", _sample_groups(), finalized=True)
    assert isinstance(data, bytes) and len(data) > 0

    doc = docx.Document(io.BytesIO(data))  # must open without error
    text = "\n".join(p.text for p in doc.paragraphs)

    assert "Maji Bora Community Initiative" in text          # org name in the title
    assert "African Women's Development Fund (AWDF) Grants" in text  # grant heading
    assert "Problem Statement — AWDF" in text                # section heading
    assert "[ORG TO PROVIDE]" in text                        # marker preserved
    assert "never submits applications" in text              # disclaimer present
    # The leading "## Problem / Need Statement" markdown heading is stripped
    # (the Word heading replaces it), so it should not appear as literal text.
    assert "## Problem / Need Statement" not in text


def test_build_docx_highlights_markers():
    data = build_docx("Org", _sample_groups())
    doc = docx.Document(io.BytesIO(data))
    # Find the run carrying the marker and confirm it is emphasized (bold).
    marker_runs = [r for p in doc.paragraphs for r in p.runs if r.text == "[ORG TO PROVIDE]"]
    assert marker_runs, "expected a dedicated run for the marker"
    assert all(r.bold for r in marker_runs)
