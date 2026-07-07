/* ==========================================================================
   GrantScout web UI — vanilla JS (no build step, works offline).
   Drives the ADK graph through /api/run and /api/finalize.
   ========================================================================== */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  for (const k of kids.flat()) n.append(k?.nodeType ? k : document.createTextNode(k ?? ""));
  return n;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pretty = (s) => String(s).replace(/_/g, " ");
const MARKER = "[ORG TO PROVIDE]";

let META = { focus_areas: [], org_types: [] };
let RUN = null;                 // last /api/run response
let LAST_ORG = null;            // last org payload submitted (for re-drafting)
let SELECTED = new Set();       // grant ids the user has ticked to draft
const DECISION = new Map();     // draft id -> { approved, rejected, content, original }

const EXAMPLE = {
  name: "Maji Bora Community Initiative",
  org_type: "ngo_cbo",
  country: "Kenya",
  years_operating: 2,
  registered: true, has_board: true, has_audited_accounts: false,
  budget_band: "$50k–$250k",
  focus_areas: ["health", "water_sanitation"],
  mission: "We improve community health by expanding access to clean water and sanitation in rural Kenya.",
};

/* ----------------------------- init ------------------------------------ */
async function init() {
  try {
    META = await (await fetch("/api/meta")).json();
  } catch {
    META = { focus_areas: ["health", "education", "agriculture", "climate", "water_sanitation", "gender", "youth"], org_types: ["ngo_cbo", "startup_social_enterprise"] };
  }
  // Honest mode badge: say "Gemini live" only when a key is actually configured.
  if (META.llm_live) {
    const label = $("#modeBadgeLabel");
    const badge = $("#modeBadge");
    if (label) label.textContent = "Gemini live";
    if (badge) badge.title = `${META.model || "Gemini"} writes the prose — eligibility decisions stay deterministic Python`;
  }
  buildOrgTypeSeg();
  buildFocusChips();
  $("#orgForm").addEventListener("submit", onRun);
  $("#exampleBtn").addEventListener("click", loadExample);
  $("#restartBtn").addEventListener("click", restart);
  $("#restartBtn2").addEventListener("click", restart);
  $("#finalizeBtn").addEventListener("click", onFinalize);
}

const ORG_LABELS = { ngo_cbo: "NGO / CBO", startup_social_enterprise: "Startup / social enterprise" };

function buildOrgTypeSeg() {
  const seg = $("#orgTypeSeg");
  seg.innerHTML = "";
  META.org_types.forEach((t, i) => {
    const b = el("button", { type: "button", textContent: ORG_LABELS[t] || pretty(t) });
    b.setAttribute("role", "radio");
    b.dataset.value = t;
    b.setAttribute("aria-checked", i === 0 ? "true" : "false");
    b.addEventListener("click", () => {
      seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", "false"));
      b.setAttribute("aria-checked", "true");
      $("#revenueField").hidden = t !== "startup_social_enterprise";
    });
    seg.append(b);
  });
}

function buildFocusChips() {
  const wrap = $("#focusChips");
  wrap.innerHTML = "";
  META.focus_areas.forEach((f) => {
    const c = el("button", { type: "button", className: "chip", textContent: pretty(f) });
    c.dataset.value = f;
    c.setAttribute("aria-pressed", "false");
    c.addEventListener("click", () => c.setAttribute("aria-pressed", c.getAttribute("aria-pressed") === "true" ? "false" : "true"));
    wrap.append(c);
  });
}

function loadExample() {
  const f = $("#orgForm");
  f.name.value = EXAMPLE.name;
  f.country.value = EXAMPLE.country;
  f.years_operating.value = EXAMPLE.years_operating;
  f.budget_band.value = EXAMPLE.budget_band;
  f.mission.value = EXAMPLE.mission;
  f.registered.checked = EXAMPLE.registered;
  f.has_board.checked = EXAMPLE.has_board;
  f.has_audited_accounts.checked = EXAMPLE.has_audited_accounts;
  $("#orgTypeSeg").querySelectorAll("button").forEach((b) =>
    b.setAttribute("aria-checked", b.dataset.value === EXAMPLE.org_type ? "true" : "false"));
  $("#revenueField").hidden = EXAMPLE.org_type !== "startup_social_enterprise";
  $("#focusChips").querySelectorAll(".chip").forEach((c) =>
    c.setAttribute("aria-pressed", EXAMPLE.focus_areas.includes(c.dataset.value) ? "true" : "false"));
}

/* ----------------------------- run ------------------------------------- */
function collectOrg() {
  const f = $("#orgForm");
  const orgType = $('#orgTypeSeg button[aria-checked=true]')?.dataset.value || "ngo_cbo";
  const focus = [...$("#focusChips").querySelectorAll('.chip[aria-pressed=true]')].map((c) => c.dataset.value);
  const years = f.years_operating.value.trim();
  return {
    name: f.name.value.trim(),
    org_type: orgType,
    country: f.country.value.trim(),
    focus_areas: focus,
    mission: f.mission.value.trim(),
    years_operating: years === "" ? null : Number(years),
    registered: f.registered.checked,
    has_board: f.has_board.checked,
    has_audited_accounts: f.has_audited_accounts.checked,
    revenue_model: f.revenue_model.value.trim() || null,
    budget_band: f.budget_band.value.trim() || null,
  };
}

async function onRun(e) {
  e.preventDefault();
  const errBox = $("#formError");
  errBox.hidden = true;
  const org = collectOrg();
  if (!org.name || !org.country) { showFormError("Please provide at least an organization name and country."); return; }
  if (org.focus_areas.length === 0) { showFormError("Pick at least one focus area so we can match honestly."); return; }

  setBusy("#runBtn", true);
  try {
    LAST_ORG = org;  // remember for re-drafting with a different grant selection
    const res = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(org) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    RUN = data;
    renderResults(data);
  } catch (err) {
    showFormError(err.message);
  } finally {
    setBusy("#runBtn", false);
  }
}

function showFormError(msg) { const b = $("#formError"); b.textContent = msg; b.hidden = false; }
function setBusy(sel, busy) {
  const btn = $(sel);
  btn.disabled = busy;
  $(".spinner", btn).hidden = !busy;
  $(".btn__label", btn).style.opacity = busy ? ".7" : "1";
}

/* --------------------------- render results ---------------------------- */
function renderResults(data) {
  $("#formView").hidden = true;
  $("#finalView").hidden = true;
  $("#resultsView").hidden = false;

  // SELECTED must be set BEFORE renderMatches so the checkboxes reflect it.
  SELECTED = new Set(data.selected_grant_ids || []);
  renderOrgSummary(data.org_profile);
  renderHonestyBanner(data.matches);
  renderMatches(data.matches, data.selected_grant_ids || []);
  renderDraftBar();
  $("#reviewMsg").textContent = data.review_message || "";
  renderDrafts(data.drafts || []);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderOrgSummary(p) {
  const box = $("#orgSummary");
  box.innerHTML = "";
  if (!p) return;
  box.append(el("span", { className: "name" }, p.name));
  const tag = (label, val) => { const t = el("span", { className: "tag" }); t.innerHTML = `${esc(label)} <strong>${esc(val)}</strong>`; return t; };
  box.append(tag("type", ORG_LABELS[p.org_type] || pretty(p.org_type)));
  box.append(tag("country", p.country));
  box.append(tag("focus", (p.focus_areas || []).map(pretty).join(", ")));
  if (p.years_operating != null) box.append(tag("years", p.years_operating));
  box.append(tag("audited", p.has_audited_accounts ? "yes" : "no"));
}

function renderHonestyBanner(matches) {
  const box = $("#honestyBanner");
  box.innerHTML = "";
  const strongButGaps = matches.filter((m) => m.eligibility_status === "gaps" && m.fit_score >= 0.99);
  if (!strongButGaps.length) return;
  const b = el("div", { className: "banner" });
  b.innerHTML =
    `<svg viewBox="0 0 24 24"><path d="M12 2L1 21h22L12 2zm0 6l6.5 11h-13L12 8zm-1 4v3h2v-3zm0 4v2h2v-2z"/></svg>` +
    `<div><strong>${strongButGaps.length} grant${strongButGaps.length > 1 ? "s are" : " is"} a perfect focus fit — but you're not yet eligible.</strong> ` +
    `That's on purpose: they're ranked lower with the exact gaps to fix, so you don't sink weeks into an application you can't win.</div>`;
  box.append(b);
}

const TIERS = [
  ["eligible", "Eligible", "you meet every hard requirement"],
  ["gaps", "Not yet eligible", "fixable gaps — worth working toward"],
  ["ineligible", "Ineligible", "structural mismatch (wrong audience or region)"],
];
const STATUS_LABEL = { eligible: "Eligible", gaps: "Not yet eligible", ineligible: "Ineligible" };

function renderMatches(matches, selected) {
  const root = $("#matches");
  root.innerHTML = "";
  for (const [status, label, blurb] of TIERS) {
    const group = matches.filter((m) => m.eligibility_status === status);
    if (!group.length) continue;
    const tier = el("div", { className: `tier tier--${status}` });
    const head = el("div", { className: "tier__head" });
    head.append(el("span", { className: "tier__dot" }), `${label} `, el("span", { className: "tier__count" }, `· ${group.length} · ${blurb}`));
    tier.append(head);
    group.forEach((m) => tier.append(matchCard(m, selected)));
    root.append(tier);
  }
}

function matchCard(m, selected) {
  const g = m.grant;
  const card = el("div", { className: `match match--${m.eligibility_status}` });

  const top = el("div", { className: "match__top" });
  const left = el("div", {});
  left.append(el("div", { className: "match__title" }, g.title));
  left.append(el("div", { className: "match__funder" }, g.funder));
  const right = el("div", { className: "match__right" });
  right.append(el("span", { className: `pill pill--${m.eligibility_status}` }, STATUS_LABEL[m.eligibility_status]));
  const meter = el("div", { className: "meter" });
  meter.append(el("div", { className: "meter__label" }, `focus fit ${Math.round(m.fit_score * 100)}%`));
  const track = el("div", { className: "meter__track" });
  track.append(el("div", { className: "meter__fill", style: `width:${Math.round(m.fit_score * 100)}%` }));
  meter.append(track);
  right.append(meter);
  top.append(left, right);
  card.append(top);

  const meta = el("div", { className: "match__meta" });
  meta.append(el("span", { className: "metatag" }, `💰 ${g.value_range}`));
  meta.append(el("span", { className: "metatag" }, `🗓 ${g.deadline}`));
  meta.append(el("span", { className: "metatag" }, `📍 ${(g.country_scope || []).map(pretty).join(", ")}`));
  const src = el("span", { className: "metatag" });
  src.innerHTML = `🔗 <a href="${esc(g.url)}" target="_blank" rel="noopener">source</a> · ${esc(g.source)}`;
  meta.append(src);
  card.append(meta);

  if (m.gaps && m.gaps.length) {
    const box = el("div", { className: "gaps" });
    box.append(el("div", { className: "gaps__h" }, "What to fix to become eligible"));
    const ul = el("ul");
    m.gaps.forEach((gp) => ul.append(el("li", {}, gp)));
    box.append(ul);
    card.append(box);
  }
  // Footer: let the user choose whether to draft for this grant, and show
  // whether it is currently drafted below.
  const foot = el("div", { className: "match__foot" });
  const cb = el("input", { type: "checkbox" });
  cb.checked = SELECTED.has(g.id);
  cb.addEventListener("change", () => {
    if (cb.checked) SELECTED.add(g.id); else SELECTED.delete(g.id);
    syncDraftBar();
  });
  const lbl = el("label", { className: "pick" });
  lbl.append(cb, "Draft this grant");
  foot.append(lbl);
  if (selected.includes(g.id)) foot.append(el("span", { className: "drafted-flag" }, "✓ drafted below"));
  card.append(foot);
  return card;
}

/* -------------------------- draft selection bar ------------------------ */
function renderDraftBar() {
  const bar = $("#draftBar");
  bar.innerHTML = "";
  if (!RUN || !(RUN.matches || []).length) return;
  const info = el("div", { className: "draft-bar__info" });
  info.append("Draft for ", el("strong", { id: "pickCount" }, String(SELECTED.size)), " selected grant(s).");
  const actions = el("div", { className: "draft-bar__actions" });
  const dl = el("button", { type: "button", className: "btn btn-ghost btn-sm", textContent: "⬇ Download current drafts (.docx)" });
  dl.addEventListener("click", downloadDrafts);
  const update = el("button", { type: "button", className: "btn btn-primary btn-sm", id: "updateDraftsBtn" });
  update.innerHTML = `<span class="btn__label">Update drafts</span><span class="spinner" hidden></span>`;
  update.addEventListener("click", onDraft);
  actions.append(dl, update);
  bar.append(info, actions);
  syncDraftBar();
}

function syncDraftBar() {
  const count = $("#pickCount");
  if (count) count.textContent = String(SELECTED.size);
  const btn = $("#updateDraftsBtn");
  const dl = $("#draftBar .btn-ghost");
  if (dl) dl.disabled = !(RUN && (RUN.drafts || []).length);
  if (!btn) return;
  const current = new Set(RUN?.selected_grant_ids || []);
  const same = current.size === SELECTED.size && [...SELECTED].every((x) => current.has(x));
  btn.disabled = same;
  btn.title = same ? "Selection matches the current drafts" : "Re-draft for the selected grants";
}

async function onDraft() {
  if (!LAST_ORG) return;
  setBusy("#updateDraftsBtn", true);
  try {
    const body = { ...LAST_ORG, preferred_grant_ids: [...SELECTED], replace_session_id: RUN.session_id };
    const res = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not re-draft.");
    RUN = data;
    renderResults(data);
    $("#draftsTitle").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setBusy("#updateDraftsBtn", false);
    alert(err.message);
  }
}

/* ----------------------------- drafts ---------------------------------- */
function stripHeading(text) { return text.replace(/^#{1,6}[^\n]*\n+/, ""); }
function markerHtml(text) {
  return esc(text).split(esc(MARKER)).join(`<span class="marker">${esc(MARKER)}</span>`);
}

function renderDrafts(drafts) {
  DECISION.clear();
  const root = $("#drafts");
  root.innerHTML = "";
  if (!drafts.length) {
    root.append(el("p", { className: "muted" }, "No sections were drafted (no winnable grants selected)."));
    return;
  }
  drafts.forEach((d) => {
    DECISION.set(d.id, { approved: true, rejected: false, content: d.content, original: d.content });
    root.append(draftCard(d));
  });
}

function draftCard(d) {
  const n = (d.content.match(/\[ORG TO PROVIDE\]/g) || []).length;
  const card = el("div", { className: "draft" });
  card.dataset.id = d.id;

  const head = el("div", { className: "draft__head" });
  head.append(el("span", { className: "draft__title" }, d.title));
  head.append(el("span", { className: `badge ${n ? "badge--fill" : "badge--ready"}` }, n ? `${n} to fill` : "ready"));
  const controls = el("div", { className: "draft__controls" });
  const editBtn = el("button", { type: "button", className: "linkbtn", textContent: "Edit" });
  const rejectLabel = el("label", { className: "reject-toggle" });
  const rejectCb = el("input", { type: "checkbox" });
  rejectLabel.append(rejectCb, "Reject");
  controls.append(editBtn, rejectLabel);
  head.append(controls);
  card.append(head);

  const body = el("div", { className: "draft__body" });
  const view = el("div", { className: "draft__text" });
  view.innerHTML = markerHtml(stripHeading(d.content));
  const ta = el("textarea", { className: "draft__edit", value: d.content });
  ta.hidden = true;
  body.append(view, ta);
  card.append(body);

  editBtn.addEventListener("click", () => {
    const editing = ta.hidden;
    ta.hidden = !editing;
    view.hidden = editing;
    editBtn.textContent = editing ? "Preview" : "Edit";
  });
  ta.addEventListener("input", () => {
    const st = DECISION.get(d.id);
    st.content = ta.value;
    view.innerHTML = markerHtml(stripHeading(ta.value));
  });
  rejectCb.addEventListener("change", () => {
    const st = DECISION.get(d.id);
    st.rejected = rejectCb.checked;
    st.approved = !rejectCb.checked;
    card.classList.toggle("draft--rejected", rejectCb.checked);
  });
  return card;
}

/* ---------------------------- finalize --------------------------------- */
async function onFinalize() {
  const approved_section_ids = [];
  const rejected_ids = [];
  const edits = {};
  for (const [id, st] of DECISION) {
    if (st.rejected) { rejected_ids.push(id); continue; }
    approved_section_ids.push(id);
    if (st.content !== st.original) edits[id] = st.content;
  }
  const decision = { approved_section_ids, edits, rejected_ids, note: $("#reviewNote").value.trim() };

  setBusy("#finalizeBtn", true);
  try {
    const res = await fetch("/api/finalize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: RUN.session_id, decision }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not finalize.");
    renderFinal(data.finalized);
  } catch (err) {
    alert(err.message);
  } finally {
    setBusy("#finalizeBtn", false);
  }
}

function renderFinal(f) {
  $("#resultsView").hidden = true;
  $("#finalView").hidden = false;
  const root = $("#finalContent");
  root.innerHTML = "";

  const card = el("div", { className: "final-card" });
  const head = el("div", { className: "final-head" });
  head.innerHTML = `<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm-1.2 14.2l-4-4 1.4-1.4 2.6 2.6 5.6-5.6 1.4 1.4z"/></svg>`;
  head.append(el("div", { className: "draft__title", style: "font-size:1rem" }, "Approved & finalized"));
  head.append(el("span", { className: "not-submitted" }, "● NOT SUBMITTED"));
  card.append(head);

  const body = el("div", { className: "final-body" });
  const edited = f.sections.filter((s) => s.edited_by_human).length;
  const stats = el("div", { className: "stat-row" });
  stats.append(stat(f.approved_count, "approved"), stat(edited, "edited"), stat(f.rejected_count, "rejected"));
  body.append(stats);
  if (f.reviewer_note) body.append(el("p", { className: "muted" }, `Note: “${f.reviewer_note}”`));

  const list = el("ul", { className: "final-list" });
  f.sections.forEach((s) => {
    const li = el("li");
    li.append(el("span", {}, s.title));
    if (s.edited_by_human) li.append(el("span", { className: "edited" }, "edited"));
    const copy = el("button", { type: "button", className: "linkbtn copy", textContent: "Copy text" });
    copy.addEventListener("click", async () => { try { await navigator.clipboard.writeText(s.content); copy.textContent = "Copied ✓"; setTimeout(() => (copy.textContent = "Copy text"), 1500); } catch { copy.textContent = "Copy failed"; } });
    li.append(copy);
    list.append(li);
  });
  body.append(el("h3", { style: "margin:.6rem 0 .3rem;font-size:.9rem" }, `Sections (${f.sections.length})`), list);

  // Downloads: everything, plus one file per grant (each application separately).
  const orgName = RUN?.org_profile?.name;
  const dlRow = el("div", { className: "dl-row" });
  dlRow.append(el("span", { className: "dl-label" }, "Download as Word (.docx)"));
  const all = el("button", { type: "button", className: "btn btn-primary btn-sm", textContent: "⬇ Download all" });
  all.addEventListener("click", (e) => exportDocx({ sections: f.sections, filename: "grantscout-applications.docx", finalized: true, btn: e.currentTarget }));
  dlRow.append(all);
  for (const [gid, secs] of groupByGrant(f.sections)) {
    const b = el("button", { type: "button", className: "linkbtn", textContent: `⬇ ${grantTitleFor(gid)}` });
    b.addEventListener("click", (e) => exportDocx({ sections: secs, filename: `grantscout-${slug(gid)}.docx`, finalized: true, btn: e.currentTarget }));
    dlRow.append(b);
  }
  body.append(dlRow);

  const remaining = f.sections.reduce((acc, s) => acc + (s.content.match(/\[ORG TO PROVIDE\]/g) || []).length, 0);
  const next = el("div", { className: "next" });
  next.innerHTML = `<h3>Next steps</h3><ul>
    <li>Fill the <strong>${remaining}</strong> remaining ${esc(MARKER)} markers with real figures.</li>
    <li>Verify each grant's deadline &amp; terms at its source link.</li>
    <li><strong>Submit the applications yourself</strong> — GrantScout never submits.</li></ul>`;
  body.append(next);
  body.append(el("p", { className: "disclaimer" }, f.disclaimer || ""));

  card.append(body);
  root.append(card);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function stat(num, label) {
  const s = el("div", { className: "stat" });
  s.append(el("b", {}, String(num)), label);
  return s;
}

/* ------------------------------ export --------------------------------- */
const slug = (s) => String(s).replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase() || "grant";

function groupByGrant(sections) {
  const m = new Map();
  for (const s of sections) {
    if (!m.has(s.grant_id)) m.set(s.grant_id, []);
    m.get(s.grant_id).push(s);
  }
  return m;
}

function grantTitleFor(grantId) {
  const m = (RUN?.matches || []).find((x) => x.grant.id === grantId);
  return m ? m.grant.title : grantId;
}

function groupsFromSections(sections) {
  const out = [];
  for (const [gid, secs] of groupByGrant(sections)) {
    out.push({ grant_title: grantTitleFor(gid), sections: secs.map((s) => ({ title: s.title, content: s.content })) });
  }
  return out;
}

// Ask the server to build a Word (.docx) file and download the returned blob.
async function exportDocx({ sections, filename, finalized, btn }) {
  if (!sections || !sections.length) return;
  const fname = filename.endsWith(".docx") ? filename : filename + ".docx";
  const label = btn ? btn.textContent : null;
  if (btn) { btn.disabled = true; btn.textContent = "Preparing…"; }
  try {
    const res = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        org_name: RUN?.org_profile?.name || "",
        groups: groupsFromSections(sections),
        finalized: !!finalized,
        filename: fname,
      }),
    });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || "Export failed."); }
    downloadBlobObject(fname, await res.blob());
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = label; }
  }
}

function downloadBlobObject(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadDrafts(ev) {
  exportDocx({ sections: RUN?.drafts || [], filename: "grantscout-drafts.docx", finalized: false, btn: ev?.currentTarget });
}

function restart() {
  RUN = null;
  LAST_ORG = null;
  SELECTED = new Set();
  DECISION.clear();
  // Clear stale content so a re-run never shows a previous run's cards.
  for (const id of ["#matches", "#drafts", "#draftBar", "#honestyBanner", "#orgSummary", "#finalContent"]) $(id).innerHTML = "";
  $("#reviewNote").value = "";
  $("#finalView").hidden = true;
  $("#resultsView").hidden = true;
  $("#formView").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.addEventListener("DOMContentLoaded", init);
