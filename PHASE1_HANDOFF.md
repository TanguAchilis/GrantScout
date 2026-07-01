# GrantScout — Phase 1 Handoff (ground truth for Phase 2)

Factual record of what Phase 1 (Claude Code) actually built. Read this alongside
`grantscout.spec.yaml` when opening the project in Antigravity. **No Antigravity
prompt here — facts only.** Verified on Python 3.11.15, `google-adk==2.3.0`,
`mcp==1.28.1`, `pydantic==2.13.4`, on Windows.

---

## 1. Actual structure

```
grantscout/
  __init__.py
  agent.py            # ADK 2.0 Workflow graph: root_agent + app
  config.py           # MODEL, thresholds, vocabularies, CATALOG_PATH (no secrets)
  models.py           # Pydantic: Grant, OrgInput, OrgProfile, Match, Draft,
                      #           ReviewDecision, EligibilityRequirement
  eligibility.py      # DETERMINISTIC check_eligibility() — the honesty mechanism
  matching.py         # compute_fit / build_match / rank_matches (no ADK import)
  security.py         # pii_scrub, injection_screen, neutralize, validate_search_args
  llm.py              # llm_available() / complete() — None when no key (offline)
  ui.py               # terminal presentation layer for the CLI (color/alignment)
  nodes/
    __init__.py
    researcher.py     # researcher(ctx, node_input) -> Event
    matcher.py        # matcher(ctx) -> Event
    drafter.py        # drafter(ctx) -> Event
    review_gate.py    # review_gate(ctx) async-gen + apply_review_decision()
mcp_server/
  __init__.py
  server.py           # FastMCP: search_grants + discover_grants (stdio)
  catalog.json        # 30 curated grants under top-level key "grants"
  catalog_search.py   # load_catalog(), search_grants() — backs MCP + matcher
  discovery.py        # discover_grants(), normalize_listing() (screens web text)
web/                  # ADDED (user request): local interactive UI, machine-independent
  __init__.py
  server.py           # Starlette: /api/run, /api/finalize, /api/export, /api/meta
  docx_export.py      # build_docx(): Word export via python-docx (testable, no server)
  static/
    index.html        # single-page shell + org form
    styles.css        # design system (tokens + components)
    app.js            # vanilla JS: run -> matches/drafts -> review gate -> finalize -> .docx
tests/
  __init__.py
  conftest.py         # make_grant() / make_profile() builders + fixtures
  test_eligibility.py # incl. the "looks like a fit but fails a hard req" case
  test_matching.py    # incl. eligible-outranks-higher-fit-but-ineligible
  test_security.py    # pii_scrub, injection_screen (both directions), validators
  test_catalog.py     # >=25 entries, attribution, filtering
  test_discovery.py   # injection screening on web-sourced listings (hermetic)
  test_review_gate.py # apply_review_decision: approve/edit/reject + never-submitted
  test_docx_export.py # build_docx opens as a valid .docx; markers highlighted
```

Also at repo root: `run_local.py`, `run_web.py`, `pyproject.toml`, `uv.lock`,
`.gitignore`, `.env.example`, `README.md`, `data/.gitkeep`, `.claude/launch.json`.

---

## 2. ADK import reality (exact lines used, verbatim)

The prompt suggested `from google.adk import Workflow` and
`from google.adk.events import RequestInput`. **Those are NOT the real ADK 2.x
paths** — see Deviations §7. The imports actually used and verified to work:

```python
# grantscout/agent.py
from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import FunctionNode, Workflow

# grantscout/nodes/researcher.py, matcher.py, drafter.py
from google.adk.agents.context import Context
from google.adk.events.event import Event

# grantscout/nodes/review_gate.py
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput

# run_local.py
from google.adk.runners import InMemoryRunner
from google.genai import types

# grantscout/llm.py  (guarded; only imported when a key is configured)
from google import genai
from google.genai import types
```

- **`LlmAgent` is NOT used.** `from google.adk.agents import LlmAgent` exists and
  imports fine, but the three reasoning nodes are **function nodes**, not LlmAgent
  (deliberate — see Deviations §7).
- The review gate is wrapped explicitly:
  `_review_gate_node = FunctionNode(func=review_gate, rerun_on_resume=True)`.
  `rerun_on_resume=True` is **required** — with the FunctionNode default (`False`)
  the human response becomes the node output and `state.finalized` is never
  written. This was verified empirically.

---

## 3. Entry point & how the runner invokes the graph

- **Root agent:** `grantscout/agent.py` defines
  `root_agent = Workflow(name="grantscout", input_schema=OrgInput, edges=[...])`
  with edges `START→researcher→matcher→drafter→_review_gate_node`.
  (`root_agent` is the ADK-convention symbol Phase 2 / agents-cli will look for.)
- **App:** the same file defines
  `app = App(name="grantscout_app", root_agent=root_agent,
  resumability_config=ResumabilityConfig(is_resumable=True))`.
  Resumability is required for the HITL gate.
- **Local runner (`run_local.py`):**
  1. `InMemoryRunner(app=app)`, then `session_service.create_session(...)`.
  2. **Pass 1:** `run_async(new_message=Content(text=OrgInput.model_dump_json()))`.
     START parses the JSON into `OrgInput` (via `input_schema`). Streams until the
     gate emits a function call `adk_request_input` (id `"review"`,
     `long_running_tool_ids={"review"}`); the workflow suspends.
  3. Builds a `ReviewDecision`, sends **Pass 2:** `run_async(new_message=Content(
     parts=[Part(function_response=FunctionResponse(id="review",
     name="adk_request_input", response=decision.model_dump()))]))`. The gate
     re-runs, applies the decision, writes `state.finalized`.

---

## 4. Catalog

- **Path:** `mcp_server/catalog.json` (top-level object; entries under `"grants"`,
  with an `"_about"` provenance/attribution block).
- **Count:** **30** entries (spec minimum is 25). Asserted by
  `tests/test_catalog.py::test_catalog_has_at_least_25_entries`.
- **Public sources consolidated** (every entry has a `source` attribution to one
  of these): AfricanNGOs.org funding roundups, FundsforNGOs Africa listings,
  GlobalGiving / Instrumentl Africa browse pages, Africa-Grants.com latest grants.
- Mix of `ngo_cbo`, `startup_social_enterprise`, and both. `eligibility_requirements`
  are **structured objects** (`code`/`value`/`label`), not free strings — see §7.
- Funder programs are real; deadlines use `rolling`/`annual` or ISO dates and
  should be re-verified at the entry `url`. No grants invented.

---

## 5. Test + run status

```bash
uv venv --python 3.11
uv pip install -e ".[dev,web]"
uv run pytest -q            # -> 39 passed
uv run python run_local.py  # CLI: one full pipeline turn
uv run python run_web.py    # web UI at http://127.0.0.1:8000
```

- **`pytest`: GREEN — 39 passed.** Tests are hermetic (no network, no API key).
  Most import only the pure-Python core; `test_review_gate.py` also imports the
  review-gate node (pulls in `google-adk`), and `test_docx_export.py` needs
  `python-docx` (it `importorskip`s cleanly if the `web` extra isn't installed).
- **`run_local.py`: completes ONE full pipeline turn** —
  `researcher → matcher → drafter → [review-gate PAUSE] → finalize` — offline.
  Observed: 9 matches (7 eligible, 2 gaps); the two 100%-focus-fit WASH funders
  (WaterAid, Conrad N. Hilton) are correctly ranked **last** with gaps shown
  ("Requires 3+ years operating; you reported 2", "Requires audited accounts...").
  Finalized package is stamped `submitted: false`.
- **`run_web.py`: verified end-to-end in a browser.** `/api/run` (200) runs the
  graph to the gate; the UI renders grouped matches + drafts; `/api/finalize`
  (200) resumes the real HITL gate with a `ReviewDecision`. Confirmed reject+edit:
  editing one section and rejecting another yields "3 approved, 1 edited,
  1 rejected" with the rejected section excluded. User grant-selection re-drafts
  through the graph (2→3 grants → 6 sections). `/api/export` (200) returns a valid
  `.docx` (ZIP `PK` signature, correct MIME, ~37 KB). Mobile layout collapses to
  one column; status colors/fit-meter computed styles verified.
- MCP server smoke-tested: `mcp.list_tools()` -> `['search_grants',
  'discover_grants']`; malformed input raises `ValueError`. Run standalone with
  `python -m mcp_server.server` (stdio).

---

## 6. PHASE 2 markers (every `# PHASE 2` stub)

| File:line | Note |
|-----------|------|
| `grantscout/agent.py:30` | If a reviewer prefers literal `LlmAgent` nodes, the three function nodes can be swapped for `LlmAgent(..., output_schema=...)` in the edges without touching eligibility/matching/catalog. (Optional.) |
| `grantscout/llm.py:48` | The real Gemini `complete()` call path is only EXERCISED once `GOOGLE_API_KEY`/ADC is configured. In Phase 1 there is no key, so it returns `None` and the deterministic fallbacks run. No node changes needed to enable it. |

There are **no other Google-tooling stubs** — agents-cli, real `.env`, dry-run, and
deploy were intentionally not started (Phase 1 boundary). `.env.example` holds
placeholders only.

---

## 7. Surprises / deviations (do NOT "fix" these in Phase 2)

1. **ADK import paths differ from the prompt.** Real paths are
   `from google.adk.workflow import Workflow` and
   `from google.adk.events.request_input import RequestInput` (not
   `from google.adk import Workflow` / `from google.adk.events import RequestInput`).
   Verified against `google-adk==2.3.0` and the ADK Workflow reference. Used the
   real paths.
2. **Reasoning nodes are FUNCTION nodes, not `LlmAgent`.** The spec labels
   researcher/matcher/drafter `kind: llm_agent`. They are implemented as function
   nodes that call the LLM only for prose, because (a) eligibility pass/fail and
   ranking must be deterministic Python — putting an LlmAgent "in charge" of the
   verdict is the exact flattery failure the project avoids — and (b) function
   nodes run fully offline with no key, satisfying the Phase-1 "runs locally"
   requirement. The graph topology and the spec's edges are unchanged. This is
   arguably *more* faithful to "the LLM explains gaps; it does not decide".
3. **`eligibility_requirements` are structured objects, not strings.** The spec's
   `catalog` section shows example requirement *strings*. They are encoded as
   `{code, value?, label}` records so `eligibility.py` can decide pass/fail
   deterministically (the whole honesty mechanism). Each record keeps a human
   `label`, so nothing readable is lost. Codes: `registered_entity`,
   `min_years_operating`, `audited_accounts`, `functioning_board`, `org_type`.
4. **Gate uses `rerun_on_resume=True` (must keep).** Required for the HITL resume
   to write `state.finalized`; the FunctionNode default would silently break it.
5. **`Grant` has 3 optional discovery-only fields** (`description`, `discovered`,
   `injection_flagged`), defaulted so catalog entries are unaffected. Discovered
   web entries carry screened/neutralized text + flags here.
6. **Matcher calls `search_grants` in-process**, not via an MCP client subprocess —
   the same implementation (`catalog_search.search_grants`) backs both the MCP
   server and the node, keeping the offline demo dependency-free. The MCP server
   genuinely exposes the identical tool over stdio.
7. **`discover_grants` is off by default in the pipeline** (set
   `GRANTSCOUT_ENABLE_DISCOVERY=1` to enable). Its fetch is best-effort and returns
   `[]` on any failure so it can never break the catalog spine. The
   security-critical screening (`normalize_listing`) is unit-tested hermetically.
8. **`ResumabilityConfig` emits an `[EXPERIMENTAL]` warning** in ADK 2.3; expected,
   filtered in `run_local.py` / `web/server.py` for clean output.
9. **A web UI (`web/`, `run_web.py`) and a CLI presentation layer (`grantscout/ui.py`)
   were added at the user's request** — not in the original spec. Both are
   machine-independent and use NO Google tooling (Starlette + uvicorn, already
   present via the MCP SDK; declared under the `web` extra). The web server drives
   the exact same `app`/graph as the CLI; it does not reimplement any agent logic.
   The review-gate message (`REVIEW_MESSAGE`) was expanded to enumerate the human's
   options (approve/edit/reject) so the HITL pause is self-explanatory in both the
   CLI and web UI. None of this touches eligibility/matching/catalog/MCP logic.
10. **User grant-selection + Markdown export (user request).** `OrgInput` gained an
    optional `preferred_grant_ids: list[str] | None`, so the human's choice of which
    grants to draft flows through the SAME graph (matcher uses
    `matching.select_grant_ids`; `None` = auto-pick top winnable, `[]` = none,
    `[ids]` = exactly those). The web UI re-drafts by calling `/api/run` again with
    that field — it re-runs the deterministic graph (fast offline; Phase 2's LLM
    path would re-run too). Export is **Word (.docx)** via a server endpoint
    (`/api/export` -> `web/docx_export.build_docx`, using `python-docx` in the
    `web` extra) so non-technical users get a ready-to-edit document; the client
    downloads the returned blob (all sections or one file per grant, with
    `[ORG TO PROVIDE]` markers highlighted).

---

## 8. Secret check

- **No `.env` file exists** in the repo (only `.env.example` with placeholders).
- `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), `data/*`,
  `__pycache__`, `.venv`.
- Scanned all committed `*.py`/`*.json`/`*.toml`/`*.md`/`*.example`/`*.lock` for
  key patterns (`AIza…`, `sk-…`, `ya29.`, `AKIA…`, PEM headers): **none found.**
- No key is read or hardcoded anywhere; `llm.py` reads `GOOGLE_API_KEY` from the
  environment at call time only.
