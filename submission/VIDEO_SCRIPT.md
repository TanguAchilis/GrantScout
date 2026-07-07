# GrantScout — video script (≤ 5:00)

**Target: 4:50.** Narration is written for ~145 words/minute — read it naturally and the timing works out.
Record narration over the visuals listed per beat. On Windows 11 you can assemble everything in **Clipchamp**
(pre-installed): drop the clips/images on the timeline, record voiceover with the mic button, export 1080p.

**Ready-made assets** (all in this repo):

| Asset | Use in |
|---|---|
| `submission/screenshots/cover_image.png` | Beat 1 title card |
| `submission/screenshots/05_architecture.png` | Beat 3 architecture |
| `submission/video/demo_footage.mp4` (silent screen recording, 2:23, **explanatory captions baked in** — Cameroon example org, recorded with the **Gemini-live** path) | Beat 4 demo |
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

## Beat 3 — Architecture — 0:55–1:35
**Show:** `05_architecture.png` full-screen. Point (cursor or highlight) at each node as you name it.

> Here's the architecture. An ADK 2.0 workflow graph — a straight spine: researcher, matcher, drafter, review gate.
> The researcher normalizes the profile and scrubs PII before any model sees it. The matcher calls a real MCP server — search_grants — over a curated catalog of thirty source-attributed African grants, and here's the key design decision: **eligibility pass-fail is decided in plain Python, never by the LLM.** Language models round up — they tell a hopeful NGO it "looks eligible". Our verdict is deterministic, unit-tested, and can't be talked into a yes. The LLM only explains the gaps.
> The review gate is a real ADK RequestInput pause — the graph genuinely suspends until a human decides.

## Beat 4 — Demo — 1:35–4:00
**Show:** `submission/video/demo_footage.mp4`. It has explanatory **captions baked in**, so it works even while you breathe between lines — the narration below adds color on top; nudge clips ±2s in the editor if needed.

*(footage: profile form, governance switches — note the "Gemini live" badge top-right)*
> Everything you're seeing runs locally, with live Gemini calls writing the prose — see the badge. I describe my organization once — Jeunesse Avenir Cameroun, a youth-livelihoods NGO in Bafoussam, Cameroon: two years old, registered, with a board, but **no audited accounts yet**. These governance switches are honesty switches — leaving one off becomes a visible gap, not a hidden lie.

*(footage: results appear, honesty banner)*
> One click, and the graph runs — researcher, matcher against the MCP catalog, then Gemini drafting grounded prose. Top of the results: the honesty banner. One grant is a *perfect* focus fit — and GrantScout tells me straight that I'm **not eligible for it yet**.

*(footage: scrolling ranked matches — eligible tier, then the gaps tier)*
> Matches are ranked with fit and eligibility scored separately. Grants we can win today come first — like the GlobalGiving Accelerator, one hundred percent fit *and* eligible. And down here, ranked lower on purpose: the Mastercard Foundation's Fund for Rural Prosperity — one hundred percent focus fit, but it requires audited accounts we don't have, and it says so, with the exact fix. That verdict comes from deterministic Python, not from a model that can be flattered into a yes.

*(footage: ticking one more grant, "Update drafts" re-run)*
> I stay in control of scope too: tick one more grant — Davis Projects for Peace — and the graph re-drafts on demand.

*(footage: drafts + review gate, edit, reject, finalize)*
> For every selected grant, GrantScout drafts the two highest-value sections. Anything it can't verify is an explicit "ORG TO PROVIDE" marker — never an invention. At the review gate the ADK graph is genuinely paused: I edit a section inline… reject one that isn't good enough… and approve the rest.

*(footage: finalized package, NOT SUBMITTED, Word downloads, start over)*
> The finalized package is stamped **NOT SUBMITTED** — GrantScout has no submission capability at all. It exports to Word, all together or one file per grant, and hands the real next steps back to a human.

## Beat 5 — The build (Antigravity + agents-cli) — 4:00–4:40
**Show (record yourself — this is the only place these can be demonstrated):**
1. **Antigravity** with this project open — show the agent panel doing a real task (e.g. ask it to explain `grantscout/agent.py`); make sure the Antigravity branding is visible on screen. (~20s)
2. A terminal running `agents-cli info` or showing `agents-cli-manifest.yaml`. (~8s)
3. `uv run pytest -q` scrolling to **39 passed** — flash the security tests (`tests/test_security.py`). (~7s)

> GrantScout was vibe-coded in two phases. Phase one built everything machine-independent against a written spec — the graph, the MCP server, the eligibility engine, and a thirty-nine test suite covering the security screens. Phase two, here in Antigravity with the Google Agents CLI, wired up the real Gemini calls with quota-aware retry, plus the Agent Runtime deployment target in the manifest.

## Beat 6 — Close — 4:40–4:55
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
