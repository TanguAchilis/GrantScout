"""
Tests for the human-in-the-loop decision logic (apply_review_decision). This is
the pure core of the review gate — it turns drafts + a human ReviewDecision into
the finalized package, and it must (a) respect approvals/edits/rejections and
(b) always mark the output as NOT submitted.
"""
from __future__ import annotations

from grantscout.models import Draft, ReviewDecision
from grantscout.nodes.review_gate import apply_review_decision


def _drafts() -> list[Draft]:
    return [
        Draft(id="g1::problem_statement", grant_id="g1", section_type="problem_statement",
              title="Problem — G1", content="Original problem text [ORG TO PROVIDE]."),
        Draft(id="g1::funder_alignment", grant_id="g1", section_type="funder_alignment",
              title="Alignment — G1", content="Original alignment text."),
    ]


def test_approve_all_with_no_edits():
    decision = ReviewDecision(approved_section_ids=["g1::problem_statement", "g1::funder_alignment"])
    out = apply_review_decision(_drafts(), decision)
    assert out["approved_count"] == 2
    assert out["rejected_count"] == 0
    assert all(not s["edited_by_human"] for s in out["sections"])
    # The hard boundary: never submitted.
    assert out["submitted"] is False
    assert out["submitted_by_agent"] is False


def test_edit_is_applied_and_flagged():
    decision = ReviewDecision(
        approved_section_ids=["g1::problem_statement"],
        edits={"g1::problem_statement": "Edited problem text with real figures."},
    )
    out = apply_review_decision(_drafts(), decision)
    assert out["approved_count"] == 1
    sec = out["sections"][0]
    assert sec["content"] == "Edited problem text with real figures."
    assert sec["edited_by_human"] is True


def test_reject_wins_over_approve():
    # A section both approved AND rejected must NOT be finalized (reject wins).
    decision = ReviewDecision(
        approved_section_ids=["g1::problem_statement", "g1::funder_alignment"],
        rejected_ids=["g1::funder_alignment"],
    )
    out = apply_review_decision(_drafts(), decision)
    ids = [s["id"] for s in out["sections"]]
    assert ids == ["g1::problem_statement"]
    assert out["rejected_count"] == 1


def test_unknown_approved_id_is_ignored():
    decision = ReviewDecision(approved_section_ids=["does-not-exist"])
    out = apply_review_decision(_drafts(), decision)
    assert out["approved_count"] == 0
    assert out["sections"] == []
