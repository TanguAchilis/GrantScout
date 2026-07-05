# GrantScout — honest grant discovery & drafting for African NGOs and social enterprises

**Subtitle:** An ADK 2.0 multi-agent pipeline that finds African grants you can actually win, drafts the two highest-value application sections, and pauses for human review. It surfaces eligibility gaps honestly and never submits anything.

**Track:** Agents for Good

**Video:** [PASTE YOUTUBE LINK]
**Code:** [PASTE PUBLIC GITHUB REPO LINK]

---

## The problem

African NGOs, community-based organizations, and social enterprises run on grant funding, but unlike the US (Grants.gov), there is no single free official African-grants API. Real funding opportunities are abundant yet scattered across newsletters, blog roundups, and gated platforms. Two failures follow:

1. **Discovery is hard.** Finding opportunities you actually qualify for means trawling many sources by hand, every month.
2. **Honesty is rare.** Tools and hopeful humans alike over-state readiness. A three-person community organization that spends three weeks writing a proposal for a funder that requires audited accounts it does not have has been *actively harmed* by whoever told it "looks like a great fit!". For small organizations, wasted proposal-writing time is not an inconvenience; it is the scarcest resource they have.

The second failure is the one almost nobody builds for, because optimism demos better. GrantScout is built around fixing it.

## Why agents?

This problem is genuinely agentic: it needs (a) tool calls against a structured catalog and, optionally, the live web; (b) multi-step reasoning that transforms a messy organizational profile into ranked, explained matches and grounded draft text; and (c) a hard requirement that a human stays in control of anything consequential. A single prompt cannot do this; a pipeline of specialized agents with tools, deterministic checks, and a real human-in-the-loop pause can.

Equally important is what the agent must **not** do. Grant applications are high-stakes, so GrantScout is deliberately a *drafting copilot with brakes*: the LLM never decides eligibility, every unverifiable fact is an explicit `[ORG TO PROVIDE]` marker rather than an invention, and the system never submits anything anywhere.

## The solution

GrantScout consolidates 30 real, source-attributed African funding opportunities from public roundups (AfricanNGOs.org, FundsforNGOs, GlobalGiving/Instrumentl, Africa-Grants.com) into one queryable MCP catalog — that consolidation is itself a contribution, since no such free API exists. On top of it runs a four-node ADK 2.0 workflow:

**researcher → matcher → drafter → review_gate**

The user describes their organization once (type, country, years operating, governance, focus areas, mission). GrantScout returns ranked matches where **fit and eligibility are scored separately**, drafts a Problem Statement and Funder Alignment section for the grants worth pursuing, and pauses at a real human review gate where each section can be approved, edited inline, or rejected. The finalized package exports to Word (.docx) and is stamped `submitted: false`.

Both audiences (NGOs/CBOs and startups/social enterprises) run through one pipeline; `org_type` is a profile field that drives eligibility scoring, not a branch in the graph.

## Architecture

*(See the architecture diagram in the media gallery.)*

- **ADK 2.0 Workflow graph** (`grantscout/agent.py`): a straight spine `START → researcher → matcher → drafter → review_gate`, built with `google-adk==2.3.0`'s Workflow API, wrapped in an `App` with `ResumabilityConfig(is_resumable=True)` so the human-in-the-loop pause can genuinely suspend and resume the graph.
- **researcher** normalizes the profile and PII-scrubs all free text (emails, phone numbers, embedded credentials) before any LLM or trace sees it.
- **matcher** calls the `search_grants` tool, scores focus-area fit and eligibility independently, and ranks honestly: an *eligible* grant outranks a higher-fit grant the org cannot win.
- **drafter** produces two grounded sections per selected grant. Anything the organization must supply (beneficiary numbers, budgets, evidence) is an explicit `[ORG TO PROVIDE]` marker; the LLM is used only to polish prose, and a guard rejects any polish that drops a marker.
- **review_gate** is a real ADK `RequestInput` pause (a `FunctionNode` with `rerun_on_resume=True`). The human's approve/edit/reject decision resumes the graph, and this node is the *only* writer of `state.finalized`.

### MCP server

`mcp_server/server.py` (FastMCP, stdio) exposes two tools:

- `search_grants(focus_areas, country, org_type, max_deadline)` filters the curated catalog. Each grant carries structured `eligibility_requirements` (`{code, value, label}` records) so eligibility can be decided deterministically, plus a `source` attribution and funder URL.
- `discover_grants(focus_areas, country)` is an optional live-web freshness layer over public roundup pages. Every fetched description is screened for prompt injection and scrubbed of PII before it is returned; it is off by default and fails closed (returns `[]`) so it can never break the catalog spine.

The same implementations back both the MCP server and the in-process matcher, so the tool contract is identical over MCP or direct calls.

### The honesty mechanism (the most important part)

**Eligibility pass/fail is decided in plain Python (`grantscout/eligibility.py`), never by the LLM.** Whether an org meets a funder's hard requirements — right org type, in scope country, legally registered, 3+ years operating, audited accounts, functioning board — is a factual, checkable question. Language models reliably round up: they tell a hopeful NGO it "looks eligible" because the framing rewards optimism. That is precisely the failure this project exists to avoid, so the verdict lives where it is auditable, unit-tested, and cannot be talked into a yes. The LLM only *explains* gaps in plain language.

There are three honest outcomes: **eligible** (meets every hard requirement), **gaps** (fails a *fixable* requirement — "not yet eligible", with a concrete action list), and **ineligible** (fails a *structural* one — stated plainly, ranked last). You can see the mechanism working in the screenshots: WaterAid and the Conrad N. Hilton Safe Water Initiative come back at **100% focus fit but ranked last**, each with the exact fixes shown ("Requires 3+ years operating; you reported 2", "Requires audited accounts; you do not report having them"). A conventional matcher would have put those two at the top and cost the org weeks.

### Security

`grantscout/security.py` implements defense in depth:

- **Secrets via environment only** — no keys in code or git; `.env` is gitignored and the repo was scanned for key patterns before publishing.
- **Input validation** at the MCP boundary — malformed tool payloads are rejected with `ValueError`.
- **PII scrubbing** — emails, phone numbers, and URL-embedded credentials are redacted before text reaches an LLM or a trace, in the researcher and on all discovered web text.
- **Prompt-injection screening** on untrusted web data — adversarial instructions in fetched grant descriptions are detected and neutralized as inert `UNTRUSTED_DATA` (quote-and-flag, never obey), with tests covering both directions.
- **Least privilege** — each node calls only the tools it needs; only the review gate can finalize; the agent has no submission capability at all.

## What the judges can run

Everything runs locally with no API key: `uv pip install -e ".[dev,web]"`, then `uv run python run_web.py` for the full interactive web UI (or `run_local.py` for a scripted CLI turn). With no key, the reasoning nodes use deterministic fallbacks so the catalog + eligibility + review-gate spine works end-to-end offline; setting `GOOGLE_API_KEY` lights up the Gemini prose path (with 429-aware retry and quota-conscious batching). The MCP server also runs standalone: `python -m mcp_server.server`. The test suite (39 tests, hermetic) covers eligibility edge cases, honest ranking, both security screens, catalog integrity, discovery screening, and the review gate.

The screenshots in the media gallery walk the real product: (1) the org profile form with honest governance switches; (2) ranked matches with the honesty banner and the two perfect-fit-but-not-yet-eligible grants ranked last with their fix lists; (3) drafted sections with highlighted `[ORG TO PROVIDE]` markers at the human review gate; (4) the finalized package — "3 approved, 0 edited, 1 rejected", stamped NOT SUBMITTED, with per-grant Word downloads.

## Course concepts demonstrated

| Concept | Where |
|---|---|
| Agent / multi-agent system (ADK) | `grantscout/agent.py` — ADK 2.0 Workflow graph of four nodes with resumability (code) |
| MCP server | `mcp_server/server.py` — FastMCP with `search_grants` + `discover_grants` over stdio (code) |
| Security features | `grantscout/security.py` + tests — PII scrub, injection screen, validation, env-only secrets, least privilege (code) |
| Human-in-the-loop | `grantscout/nodes/review_gate.py` — real `RequestInput` pause/resume (code + video) |
| Agent skills / Agents CLI | Project scaffolded and managed with `agents-cli` (`agents-cli-manifest.yaml`, Agent Runtime target) (code + video) |
| Antigravity | Google-tooling phase built in Antigravity — shown in the video |

## The build (vibe coding journey)

GrantScout was built in two deliberate phases, entirely through vibe coding with AI coding agents. Phase 1 produced everything machine-independent — the graph, MCP server, curated catalog, deterministic eligibility engine, security utilities, both UIs, and the test suite — against a written spec (`grantscout.spec.yaml`), with a factual handoff document (`PHASE1_HANDOFF.md`) recording every deviation discovered along the way (for example, the real ADK 2.x import paths, and why `rerun_on_resume=True` is required for the resume to write finalized state). Phase 2, in Antigravity with the Google Agents CLI, wired up the Google tooling: real Gemini calls with quota-aware retry, agents-cli scaffolding with an Agent Runtime deployment target, and the demo captured in the video. The two-phase, spec-and-handoff workflow is itself a vibe-coding practice we would recommend: it kept the honest-by-construction core testable and offline, and made the cloud integration a thin, verifiable layer on top.

## Limitations and next steps

The catalog is curated, not live; entries carry source attributions and funder URLs, and users are told to verify current deadlines at the source (deadlines drift on funder sites). `discover_grants` is best-effort freshness, not coverage. Next steps: scheduled catalog refresh with human review, more grant sections (budget narrative, M&E), country-specific compliance checklists, and partnerships with the roundup publishers whose public work the catalog credits.

GrantScout's core claim is simple: for organizations whose scarcest resource is time, **an honest "not yet, and here's what to fix" is worth more than a flattering maybe** — and building that honesty into the architecture, rather than the prompt, is what makes an agent trustworthy enough to help.
