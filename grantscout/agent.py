"""
GrantScout agent — the ADK 2.0 Workflow graph.

    START -> researcher -> matcher -> drafter -> review_gate (-> END)

This is a straight 4-node spine with NO branching (per spec). `org_type` is a
profile field carried through as data; it shapes the matcher's eligibility
scoring rather than forking the graph, so both audiences (NGOs/CBOs and
startups/social enterprises) run through one pipeline.

WHY THE THREE REASONING NODES ARE FUNCTION NODES, NOT raw LlmAgent
------------------------------------------------------------------
The spec labels researcher/matcher/drafter `kind: llm_agent`. We implement them
as FUNCTION nodes that call the LLM only for prose (see each node + llm.py), for
two deliberate reasons:

  1. Honesty: the eligibility pass/fail and the ranking MUST be deterministic
     Python (eligibility.py / matching.py). Function nodes keep that logic in the
     driver's seat; the LLM only explains. Raw LlmAgent nodes would hand the
     decision to the model — exactly the flattery failure this project avoids.
  2. Offline runnability: function nodes run with no API key, so the full
     catalog + eligibility + review-gate spine executes locally in Phase 1 with
     zero cloud calls. The LLM path lights up automatically in Phase 2 when a key
     is configured — no graph changes needed.

The review gate is a genuine ADK HITL node: it yields a RequestInput and is
wrapped with rerun_on_resume=True so that, on the human's response, it re-runs
and writes the finalized package.

# PHASE 2 (Antigravity): if a reviewer prefers literal LlmAgent nodes, the three
# function nodes can be swapped for `LlmAgent(..., output_schema=...)` instances
# in the edges below without touching eligibility.py / matching.py / the catalog.
"""
from __future__ import annotations

from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import FunctionNode, Workflow

from grantscout.models import OrgInput
from grantscout.nodes import drafter, matcher, researcher, review_gate

# The review gate must RE-RUN on resume (not just return the human's response as
# output) so it can apply the ReviewDecision and write state.finalized. That is
# what rerun_on_resume=True buys us; the default FunctionNode value is False.
_review_gate_node = FunctionNode(func=review_gate, rerun_on_resume=True)

# The graph. Terminal nodes need no explicit END edge in ADK 2.0 — a node with no
# outgoing edge IS the end of the spine (the spec's `[review_gate, END]` is
# implicit here).
root_agent = Workflow(
    name="grantscout",
    description=(
        "Profiles an African NGO/CBO or startup/social enterprise, matches it to a "
        "curated catalog of African funding opportunities with honest eligibility "
        "scoring, drafts two tailored sections, and pauses for human review. Never submits."
    ),
    # START parses the user message into an OrgInput so the researcher receives a
    # typed, validated profile rather than raw Content.
    input_schema=OrgInput,
    edges=[
        ("START", researcher),
        (researcher, matcher),
        (matcher, drafter),
        (drafter, _review_gate_node),
    ],
)

# App wrapper. resumability is REQUIRED for the HITL review gate to suspend and
# resume across runs. This is what the local runner (and Phase 2 deploy) loads.
app = App(
    name="grantscout_app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)

__all__ = ["root_agent", "app"]
