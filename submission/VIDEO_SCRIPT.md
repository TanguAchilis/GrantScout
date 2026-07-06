# GrantScout — video script (≤ 5:00)

**Target: 4:50.** Narration is written for ~145 words/minute — read it naturally and the timing works out.
Record narration over the visuals listed per beat. On Windows 11 you can assemble everything in **Clipchamp**
(pre-installed): drop the clips/images on the timeline, record voiceover with the mic button, export 1080p.

**Ready-made assets** (all in this repo):

| Asset | Use in |
|---|---|
| `submission/screenshots/cover_image.png` | Beat 1 title card |
| `submission/screenshots/05_architecture.png` | Beat 3 architecture |
| `submission/video/demo_footage.mp4` (silent screen recording, ~2.4 min) | Beat 4 demo |
| **You must screen-record yourself:** Antigravity with this project open, `agents-cli` in a terminal, `uv run pytest -q` output | Beat 5 build |

---

## Beat 1 — The problem — 0:00–0:35
**Show:** `cover_image.png` as title card (0:00–0:08), then slow-zoom on it or cut to a montage of the scattered sources (optional: funder roundup sites in browser tabs).

> Hi, I'm Tangu, and this is GrantScout — an agent that finds African grants you can actually win.
> African NGOs and social enterprises run on grant funding, but unlike the US, there is no single free African-grants API. Real opportunities are scattered across newsletters and blog roundups.
> And there's a second, quieter problem: every tool in this space flatters you. A three-person organization that spends three weeks on a proposal for a funder that requires audited accounts it doesn't have — has been actively harmed. GrantScout is built around fixing that.

## Beat 2 — Why agents — 0:35–0:55
**Show:** keep title card or a simple slide: "tools + multi-step reasoning + a human in control".

> This is a genuinely agentic problem. It needs tool calls against a structured catalog, multi-step reasoning from a messy org profile to ranked matches and grounded drafts, and — because grant applications are high-stakes — a hard guarantee that a human stays in control. One prompt can't do that. A pipeline of specialized agents with deterministic checks can.

## Beat 3 — Architecture — 0:55–1:40
**Show:** `05_architecture.png` full-screen. Point (cursor or highlight) at each node as you name it.

> Here's the architecture. An ADK 2.0 workflow graph — a straight spine: researcher, matcher, drafter, review gate.
> The researcher normalizes the profile and scrubs PII before any model sees it. The matcher calls a real MCP server — search_grants — over a curated catalog of thirty source-attributed African grants, and here's the key design decision: **eligibility pass-fail is decided in plain Python, never by the LLM.** Language models round up — they tell a hopeful NGO it "looks eligible". Our verdict is deterministic, unit-tested, and can't be talked into a yes. The LLM only explains the gaps.
> The review gate is a real ADK RequestInput pause — the graph genuinely suspends until a human decides.

## Beat 4 — Demo — 1:40–4:05
**Show:** `submission/video/demo_footage.mp4` (it is paced to match this narration; nudge clips ±2s in the editor if needed).

*(footage: profile form, governance switches)*
> Everything you're seeing runs locally, no API key. I describe my organization once — Maji Bora, a Kenyan water-and-health NGO, two years old, registered, has a board, but **no audited accounts yet**. Notice these governance switches: leaving one off is honest — it becomes a visible gap, not a hidden lie.

*(footage: results appear, honesty banner)*
> One click, and the graph runs. Top of the results: an honesty banner. Two grants are a *perfect* focus fit — and GrantScout is telling me I'm **not eligible for them yet**.

*(footage: scrolling ranked matches — eligible tier, then the gaps tier)*
> Matches are ranked with fit and eligibility scored separately. Eligible grants first — grants we can win today. And down here, ranked last on purpose: WaterAid and the Hilton Safe Water Initiative, one hundred percent focus fit, with the exact fixes listed — "requires three-plus years operating, you reported two"; "requires audited accounts, you don't report having them." A conventional matcher would have put these at the top and cost us weeks.

*(footage: drafts + review gate, edit, reject, finalize)*
> For the grants worth pursuing, GrantScout drafts the two highest-value sections. Every fact it can't verify is an explicit "ORG TO PROVIDE" marker — never an invention. This is the human review gate: the ADK graph is genuinely paused here. I can edit a section inline… reject one that isn't good enough… and approve the rest.

*(footage: finalized package, NOT SUBMITTED, docx download)*
> The finalized package: three approved, one rejected, stamped **NOT SUBMITTED** — GrantScout has no submission capability at all. And it exports straight to Word, with the markers highlighted, ready for a human to finish.

## Beat 5 — The build (Antigravity + agents-cli) — 4:05–4:45
**Show (record yourself — this is the only place these can be demonstrated):**
1. **Antigravity** with this project open — show the agent panel doing a real task (e.g. ask it to explain `grantscout/agent.py`); make sure the Antigravity branding is visible on screen. (~20s)
2. A terminal running `agents-cli info` or showing `agents-cli-manifest.yaml`. (~8s)
3. `uv run pytest -q` scrolling to **39 passed** — flash the security tests (`tests/test_security.py`). (~7s)

> GrantScout was vibe-coded in two phases. Phase one built everything machine-independent against a written spec — the graph, the MCP server, the eligibility engine, and a thirty-nine test suite covering the security screens: PII scrubbing and prompt-injection quarantine on untrusted web data. Phase two, here in Antigravity with the Google Agents CLI, wired up the real Gemini calls with quota-aware retry, and the Agent Runtime deployment target you see in the manifest.

## Beat 6 — Close — 4:45–5:00
**Show:** back to `cover_image.png`, or the NOT SUBMITTED final screen.

> For organizations whose scarcest resource is time, an honest "not yet — and here's what to fix" is worth more than a flattering maybe. Building that honesty into the architecture, not the prompt, is what makes an agent trustworthy. Thanks for watching.

---

## Checklist before upload

- [ ] Total length ≤ 5:00 (target 4:50)
- [ ] Antigravity visibly on screen in Beat 5 (rubric concept — video is the ONLY place it can be shown)
- [ ] agents-cli shown (manifest or `agents-cli info`)
- [ ] Architecture diagram shown (Beat 3)
- [ ] Upload to YouTube as **public or unlisted** (not private)
- [ ] Paste the link into the Kaggle writeup (`[PASTE YOUTUBE LINK]`) and attach the video in the media gallery
