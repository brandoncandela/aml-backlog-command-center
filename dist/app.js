// Backlog Command Center front end. Reads data/command_center.json written by src/build.py.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const fmt = n => n.toLocaleString("en-US");
const money = n => "$" + Math.round(n).toLocaleString("en-US");
const pct = n => (n * 100).toFixed(n === 1 ? 0 : 1) + "%";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const nice = s => String(s).replace(/_/g, " ");
const dateLabel = iso => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const title = s => s.replace(/\b\w/g, c => c.toUpperCase());

const SOURCE_NAMES = { actimize: "Actimize", legacy_rules: "Legacy rules", fraud_referrals: "Fraud referrals" };
const METHOD_NAMES = {
  crosswalk: "Party key in crosswalk", cif: "Customer number", account: "Full account number",
  masked_account_name: "Last 4 digits plus name", name_dob: "Name plus date of birth",
  name_only: "Name only", ambiguous: "Name matches 2+ customers", no_match: "No customer found",
};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

let D;

fetch("data/command_center.json").then(r => r.json()).then(data => { D = data; init(); });

function init() {
  const s = D.summary, f = D.forecast, acc = D.resolution.accuracy;
  const qa = D.cases.filter(c => c.qa_sampled);
  const values = {
    alerts: fmt(s.alerts), cases: fmt(s.cases), per_case: s.alerts_per_case, breached: fmt(s.sla_breached_cases),
    precision: pct(acc.auto_precision), need_alert: f.analysts_needed_alert_level, need_case: f.analysts_needed_case_level,
    saved_pct: Math.round((1 - f.case_level_minutes / f.alert_level_minutes) * 100) + "%",
    multi: fmt(s.multi_source_cases), deadline: dateLabel(f.deadline), start: dateLabel(f.start),
    threshold: Math.round(D.resolution.auto_accept_threshold * 100) + "%",
    auto: fmt(acc.auto_accepted), review: fmt(acc.sent_to_review), wrong_guess: fmt(acc.review_name_only_guesses_wrong),
    sars: fmt(f.expected_sars), qa_n: fmt(qa.length), qa_p1: fmt(qa.filter(c => c.tier === "P1").length),
  };
  $$("[data-k]").forEach(el => { if (values[el.dataset.k] !== undefined) el.textContent = values[el.dataset.k]; });

  renderOverview();
  renderOnboarding();
  renderIdentity();
  renderQueue();
  renderCapacity();
  renderQA(qa);
  setupTabs();
  observe();
}

/* ---------- helpers ---------- */
function bars(el, rows, grey = []) {
  const max = Math.max(...rows.map(r => r[1]));
  el.innerHTML = rows.map(([label, v, shown]) => `
    <div class="barrow"><span>${esc(label)}</span>
      <div class="bar ${grey.includes(label) ? "grey" : ""}"><span style="--w:${(v / max).toFixed(3)}"></span></div>
      <span class="v">${shown ?? fmt(v)}</span></div>`).join("");
}

function observe() {
  if (reduced || !("IntersectionObserver" in window)) { $$(".reveal, .card").forEach(el => el.classList.add("in")); return; }
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }), { threshold: 0.12 });
  $$(".reveal, .card").forEach(el => { if (!el.classList.contains("in")) io.observe(el); });
}

function setupTabs() {
  const show = id => {
    $$(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.view === id));
    $$("section.view").forEach(v => v.hidden = v.id !== id);
    observe();
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };
  $$(".tabs button").forEach(b => b.addEventListener("click", () => { history.replaceState(null, "", "#" + b.dataset.view); show(b.dataset.view); }));
  const fromHash = () => {
    const id = location.hash.slice(1);
    if (id && document.getElementById(id)?.classList.contains("view")) show(id);
  };
  addEventListener("hashchange", fromHash);
  fromHash();
}

/* ---------- overview ---------- */
function renderOverview() {
  const t = D.summary.tiers;
  bars($("#tierBars"), [["P1 work first", t.P1 || 0], ["P2 next", t.P2 || 0], ["P3 routine", t.P3 || 0]]);
  bars($("#sourceBars"), D.sources.map(s => [SOURCE_NAMES[s.source] || s.label, s.loaded]));
}

/* ---------- onboarding ---------- */
function renderOnboarding() {
  const maps = Object.fromEntries(D.mappings.map(m => [m.source, m]));
  $("#sourceCards").innerHTML = D.sources.map(s => {
    const m = maps[s.source];
    const rejected = Object.values(s.rejected).reduce((a, b) => a + b, 0);
    const rejNote = Object.entries(s.rejected).map(([k, v]) => `${fmt(v)} ${k}`).join(", ");
    const fields = Object.entries(m.fields).map(([k, v]) => {
      const from = v.column ? `<code>${esc(v.column)}</code>` : v.path ? `<code>${esc(v.path)}</code>` : v.value !== undefined ? `always <code>${esc(v.value)}</code>` : "";
      const notes = [];
      if (v.ref_type) notes.push("matched as " + nice(v.ref_type));
      if (v.pad_left) notes.push(`restore leading zeros to ${v.pad_left} digits`);
      if (v.name_order) notes.push("name written " + nice(v.name_order).replace("last first", "Last, First"));
      if (v.map) notes.push(`${Object.keys(v.map).length} codes mapped to standard typologies`);
      if (v.date_formats) notes.push("dates like " + v.date_formats.map(d => d.replace(/%/g, "")).join(" or "));
      if (v.parse === "money") notes.push("money text like $4.2k or 12,345.67");
      if (v.open_values) notes.push("open when " + v.open_values.join(" or "));
      return `<tr><td>${nice(k)}</td><td>${from}</td><td>${esc(notes.join("; "))}</td></tr>`;
    }).join("");
    return `<div class="card reveal">
      <div class="controls" style="margin-bottom:4px"><h3 style="margin:0 auto 0 0">${esc(s.label)}</h3><span class="tag mono">${esc(s.file)}</span><span class="tag">${esc(m.format)}</span></div>
      <div class="funnel">
        <div><b>${fmt(s.rows_read)}</b><span>rows in the file</span></div>
        <div class="${s.duplicates ? "bad" : ""}"><b>${fmt(s.duplicates)}</b><span>duplicate rows dropped</span></div>
        <div><b>${fmt(s.closed)}</b><span>already closed, skipped</span></div>
        <div class="${rejected ? "bad" : ""}"><b>${fmt(rejected)}</b><span>${rejected ? esc(rejNote) + ", sent back" : "rejected"}</span></div>
        <div class="ok"><b>${fmt(s.loaded)}</b><span>loaded${s.missing_amount ? `, ${fmt(s.missing_amount)} with no amount` : ""}</span></div>
      </div>
      <details style="margin-top:14px"><summary style="cursor:pointer;color:var(--signal);font-weight:500;font-size:14px">Show the field mapping</summary>
        <div class="table-wrap" style="margin-top:10px"><table class="map-table"><thead><tr><th>Standard field</th><th>Comes from</th><th>Cleanup applied</th></tr></thead><tbody>${fields}</tbody></table></div>
      </details>
    </div>`;
  }).join("");
}

/* ---------- identity ---------- */
function renderIdentity() {
  const r = D.resolution;
  const order = ["crosswalk", "cif", "account", "masked_account_name", "name_dob", "name_only", "ambiguous", "no_match"];
  $("#methodTable tbody").innerHTML = order.filter(m => r.methods[m]).map(m => {
    const conf = r.method_notes[m]?.confidence ?? 0;
    const auto = conf >= r.auto_accept_threshold;
    return `<tr><td><b>${METHOD_NAMES[m] || nice(m)}</b><br><span style="color:var(--faint);font-size:12.5px">${esc(r.method_notes[m]?.reason || "No single customer fits, so nothing is guessed")}</span></td>
      <td>${conf ? Math.round(conf * 100) + "%" : "n/a"}</td><td>${fmt(r.methods[m])}</td>
      <td>${auto ? '<span class="pill P3">Automatic</span>' : '<span class="pill P2">Person reviews</span>'}</td></tr>`;
  }).join("");

  const present = new Set(D.review_queue.map(a => a.method));
  $$("#reviewFilter button").forEach(b => { if (b.dataset.f !== "all" && !present.has(b.dataset.f)) b.remove(); });
  let filter = "all", limit = 12;
  const draw = () => {
    const rows = D.review_queue.filter(a => filter === "all" || a.method === filter);
    $("#reviewTable tbody").innerHTML = rows.slice(0, limit).map(a => `<tr>
      <td><span class="mono">${esc(a.alert_id)}</span><br><span class="tag">${SOURCE_NAMES[a.source]}</span></td>
      <td>${esc(title(a.name || "(blank)"))}</td><td class="mono">${esc(a.customer_ref || "none")}</td>
      <td>${esc(a.reason)}</td><td class="mono">${a.candidates.length ? a.candidates.map(esc).join("<br>") : "none"}</td></tr>`).join("");
    $("#reviewCount").textContent = `Showing ${Math.min(limit, rows.length)} of ${fmt(rows.length)}`;
    $("#reviewMore").hidden = limit >= rows.length;
  };
  $$("#reviewFilter button").forEach(b => b.addEventListener("click", () => {
    $$("#reviewFilter button").forEach(x => x.setAttribute("aria-pressed", x === b));
    filter = b.dataset.f; limit = 12; draw();
  }));
  $("#reviewMore").addEventListener("click", () => { limit += 24; draw(); });
  draw();
}

/* ---------- case queue ---------- */
function renderQueue() {
  let tier = "all", multi = false, q = "", limit = 25, selected = null;
  const draw = () => {
    const rows = D.cases.filter(c => (tier === "all" || c.tier === tier) && (!multi || c.sources.length > 1)
      && (!q || (c.customer + " " + c.case_id + " " + c.typologies.join(" ")).toLowerCase().replace(/_/g, " ").includes(q)));
    $("#caseTable tbody").innerHTML = rows.slice(0, limit).map(c => `<tr class="click ${c.case_id === selected ? "sel" : ""}" data-id="${c.case_id}" tabindex="0">
      <td class="mono">${c.case_id}</td><td><b>${esc(c.customer)}</b><br><span style="color:var(--faint);font-size:12.5px">${nice(c.segment)} · risk ${c.risk_rating}</span></td>
      <td><span class="pill ${c.tier}">${c.tier}</span> <span style="color:var(--faint);font-size:12.5px">${c.priority_score}</span></td>
      <td>${c.alerts.length}${c.sources.length > 1 ? `<br><span style="color:var(--faint);font-size:12px">${c.sources.length} systems</span>` : ""}</td>
      <td class="${c.sla_breached ? "late" : ""}">${c.oldest_age_days}d</td><td>${money(c.total_amount)}</td></tr>`).join("")
      || `<tr><td colspan="6" class="empty">No cases match</td></tr>`;
    $("#caseCount").textContent = `Showing ${Math.min(limit, rows.length)} of ${fmt(rows.length)} cases`;
    $("#caseMore").hidden = limit >= rows.length;
    $$("#caseTable tr.click").forEach(tr => {
      const pick = () => { selected = tr.dataset.id; detail(D.cases.find(c => c.case_id === selected)); $$("#caseTable tr.sel").forEach(x => x.classList.remove("sel")); tr.classList.add("sel"); };
      tr.addEventListener("click", pick);
      tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    });
  };
  const seg = (id, attr, set) => $$(`#${id} button`).forEach(b => b.addEventListener("click", () => {
    if (id === "multiFilter") { multi = !multi; b.setAttribute("aria-pressed", multi); }
    else { $$(`#${id} button`).forEach(x => x.setAttribute("aria-pressed", x === b)); set(b.dataset[attr]); }
    limit = 25; draw();
  }));
  seg("tierFilter", "t", v => tier = v);
  seg("multiFilter", "m", () => {});
  $("#caseSearch").addEventListener("input", e => { q = e.target.value.trim().toLowerCase(); limit = 25; draw(); });
  $("#caseMore").addEventListener("click", () => { limit += 50; draw(); });
  draw();
  selected = D.cases[0].case_id; detail(D.cases[0]); draw();
}

function detail(c) {
  const total = c.score_parts.reduce((a, [, p]) => a + p, 0);
  $("#caseDetail").innerHTML = `
    <div class="controls" style="margin-bottom:2px"><span class="mono" style="color:var(--faint)">${c.case_id}</span><span class="pill ${c.tier}">${c.tier}</span>${c.qa_sampled ? '<span class="tag">In QA sample</span>' : ""}</div>
    <h3 style="font-size:22px;margin:4px 0 2px">${esc(c.customer)}</h3>
    <p style="color:var(--muted);margin:0 0 16px;font-size:14px">CIF <span class="mono">${c.cif}</span> · ${nice(c.segment)} · risk rating ${c.risk_rating}</p>
    <h3>Why it ranks here</h3>
    <div class="parts">${c.score_parts.map(([label, p]) => `<div><span>${esc(label)}</span><b>+${p}</b></div>`).join("")}
      <div class="total"><span>Priority score</span><b>${total}</b></div></div>
    <h3 style="margin-top:18px">${c.alerts.length} alerts, oldest first</h3>
    <div style="margin-bottom:8px">${c.typologies.map(t => `<span class="tag">${nice(t)}</span>`).join("")}</div>
    <ul class="timeline">${c.alerts.map(a => `<li><span>${dateLabel(a.alert_date)}</span>
      <span>${nice(a.scenario)}${a.detail ? ` · ${esc(a.detail)}` : ""}<br><span style="color:var(--faint);font-size:12px">${SOURCE_NAMES[a.source]} · <span class="mono">${a.alert_id}</span> · ${METHOD_NAMES[a.method]}</span></span>
      <span>${a.amount == null ? "no amount" : money(a.amount)}</span></li>`).join("")}</ul>`;
  if (!reduced) $("#caseDetail").animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 280, easing: "ease-out" });
}

/* ---------- capacity ---------- */
function renderCapacity() {
  const f = D.forecast;
  const start = new Date(f.start + "T12:00:00"), deadline = new Date(f.deadline + "T12:00:00");
  const last = new Date(f.scenarios[0].alert_level_clear + "T12:00:00");
  const span = last - start;
  const pos = d => ((new Date(d + "T12:00:00") - start) / span * 100).toFixed(2) + "%";
  const lane = $("#lane");
  lane.insertAdjacentHTML("beforeend", `<div class="deadline" style="left:${pos(f.deadline)}"></div><div class="dot alert"></div><div class="dot case"></div>`);
  const months = [];
  for (let d = new Date(start.getFullYear(), start.getMonth() + 1, 1); d <= last; d.setMonth(d.getMonth() + 1)) months.push(new Date(d));
  months.forEach((m, i) => { if (i % (months.length > 8 ? 2 : 1) === 0) lane.insertAdjacentHTML("beforeend", `<span class="axis" style="left:${((m - start) / span * 100).toFixed(2)}%">${m.toLocaleDateString("en-US", { month: "short", year: "2-digit" })}</span>`); });

  const update = n => {
    const s = f.scenarios.find(x => x.analysts === n);
    $("#capN").textContent = n;
    $(".dot.case", lane).style.left = pos(s.case_level_clear);
    $(".dot.alert", lane).style.left = pos(s.alert_level_clear);
    $("#capCase").textContent = dateLabel(s.case_level_clear);
    $("#capAlert").textContent = dateLabel(s.alert_level_clear);
    const caseOk = new Date(s.case_level_clear + "T12:00:00") <= deadline, alertOk = new Date(s.alert_level_clear + "T12:00:00") <= deadline;
    const v = $("#capVerdict");
    v.className = "verdict " + (caseOk ? "ok" : "bad");
    v.textContent = caseOk && alertOk ? `Both approaches finish by the deadline with ${n} analysts.`
      : caseOk ? `With ${n} analysts, working by customer meets the deadline. Working alert by alert would miss it.`
      : `${n} analysts is not enough. Working by customer needs at least ${f.analysts_needed_case_level}.`;
  };
  $("#capSlider").addEventListener("input", e => update(+e.target.value));
  update(f.analysts_needed_case_level);
  $("#capSlider").value = f.analysts_needed_case_level;

  bars($("#hourBars"), [
    ["Alert by alert", f.alert_level_minutes, fmt(Math.round(f.alert_level_minutes / 60)) + " h"],
    ["One case per customer", f.case_level_minutes, fmt(Math.round(f.case_level_minutes / 60)) + " h"],
  ], ["Alert by alert"]);

  const a = f.assumptions;
  const rows = [
    ["Review one alert on its own", a.alert_minutes + " min"], ["First alert in a case", a.case_base_minutes + " min"],
    ["Each extra alert in the same case", a.case_extra_alert_minutes + " min"], ["Fraud team evidence", a.fraud_referral_minutes + " min"],
    ["Enhanced due diligence, high risk", a.high_risk_edd_minutes + " min"], ["Identity review per alert", a.identity_review_minutes + " min"],
    ["Write and file a SAR", a.sar_minutes + " min"], ["QA review", a.qa_minutes + " min"],
    ["SAR rate P1 / P2 / P3", ["P1", "P2", "P3"].map(t => Math.round(f.escalation_rate[t] * 100) + "%").join(" / ")],
  ];
  $("#assumeTable tbody").innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
}

/* ---------- QA ---------- */
function renderQA(qa) {
  $("#qaTable tbody").innerHTML = qa.map(c => {
    const methods = [...new Set(c.alerts.map(a => METHOD_NAMES[a.method]))];
    return `<tr><td class="mono">${c.case_id}</td><td>${esc(c.customer)}</td><td><span class="pill ${c.tier}">${c.tier}</span></td>
      <td>${c.priority_score}</td><td>${c.alerts.length}</td><td style="font-size:13px;color:var(--muted)">${methods.join(", ")}</td></tr>`;
  }).join("");
}
