const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, method = "GET") => (await fetch("/api" + path, { method })).json();
const pill = (s) => `<span class="pill ${esc(s)}">${esc(s)}</span>`;
const time = (t) => (t ? t.replace("T", " ") : "—");

const views = {
  async overview() {
    const [s, jobs, appr] = await Promise.all([api("/stats"), api("/jobs"), api("/approvals")]);
    const runs = await api("/runs");
    return `<h2>Good day, admin</h2>
    <div class="cards">
      <div class="card"><div class="n">${s.jobs}</div><div class="l">scheduled jobs</div></div>
      <div class="card"><div class="n">${s.runs}</div><div class="l">runs recorded</div></div>
      <div class="card"><div class="n" style="color:var(--warn)">${s.pending}</div><div class="l">changes waiting for approval</div></div>
      <div class="card"><div class="n" style="color:var(--bad)">${s.failed}</div><div class="l">failed runs</div></div>
    </div>
    <div class="grid2"><div><h3>Job health</h3><table>${jobs.map((j) => `<tr><td>${esc(j.name)}</td><td>${j.last_run ? pill(j.last_run.status) : "—"}</td></tr>`).join("")}</table></div>
    <div><h3>What the supervisor says</h3>${runs.slice(0, 3).map((r) => `<div class="review">${esc(r.review)}</div>`).join("")}</div></div>
    <h3>Waiting for you</h3>${approvalTable(appr.filter((a) => a.state === "pending").slice(0, 4))}`;
  },
  async jobs() {
    const jobs = await api("/jobs");
    return `<h2>Scheduled jobs</h2><table><tr><th>Job</th><th>Every</th><th>Last run</th><th>Status</th><th></th></tr>
    ${jobs.map((j) => `<tr><td><b>${esc(j.name)}</b><div class="muted">${esc(j.description)}</div></td>
      <td>${j.every_minutes} min</td><td>${time(j.last_run?.finished)}</td>
      <td>${j.enabled ? (j.last_run ? pill(j.last_run.status) : "—") : '<span class="muted">paused</span>'}</td>
      <td><span class="row"><button class="btn" onclick="runJob('${j.id}')">Run now</button>
      <button class="btn ghost" onclick="toggle('${j.id}',${j.enabled})">${j.enabled ? "Pause" : "Resume"}</button></span></td></tr>`).join("")}</table>`;
  },
  async runs() {
    const runs = await api("/runs");
    return `<h2>Runs &amp; logs</h2><table><tr><th>#</th><th>Job</th><th>Finished</th><th>Status</th><th>Summary</th></tr>
    ${runs.map((r) => `<tr class="click" onclick="openRun(${r.id})"><td>${r.id}</td><td>${esc(r.job_id)}</td><td>${time(r.finished)}</td><td>${pill(r.status)}</td><td>${esc(r.summary)}</td></tr>`).join("")}</table>`;
  },
  async approvals() {
    const a = await api("/approvals");
    return `<h2>Approvals</h2><p class="muted">Agents propose changes. Nothing happens until a person approves it (demo mode only simulates the change).</p>${approvalTable(a)}`;
  },
};

function approvalTable(list) {
  if (!list.length) return `<p class="muted">Nothing waiting.</p>`;
  return `<table><tr><th>Change</th><th>Target</th><th>Why</th><th>Risk</th><th>State</th><th></th></tr>
  ${list.map((a) => `<tr><td>${esc(a.kind)}</td><td>${esc(a.target)}</td><td>${esc(a.reason)}</td><td>${pill(a.risk)}</td><td>${pill(a.state)}</td>
  <td>${a.state === "pending" ? `<span class="row"><button class="btn" onclick="decide(${a.id},'approve')">Approve</button><button class="btn no" onclick="decide(${a.id},'reject')">Reject</button></span>` : `<span class="muted">${esc(a.note)}</span>`}</td></tr>`).join("")}</table>`;
}

async function openRun(id) {
  const r = await api("/runs/" + id);
  $("#wtitle").textContent = `Run #${r.id}`;
  const keys = r.findings.length ? Object.keys(r.findings[0]) : [];
  $("#view").innerHTML = `<button class="btn ghost" onclick="show('runs')">← Back</button>
  <h2 style="margin-top:12px">${esc(r.job_id)} · run #${r.id} ${pill(r.status)}</h2>
  <div class="muted">${time(r.started)} → ${time(r.finished)}</div>
  <h3>Supervisor review</h3><div class="review">${esc(r.review)}</div>
  <h3>Findings (${r.findings.length})</h3>${r.findings.length ? `<table><tr>${keys.map((k) => `<th>${esc(k)}</th>`).join("")}</tr>${r.findings.map((f) => `<tr>${keys.map((k) => `<td>${k === "level" ? pill(f[k]) : esc(f[k])}</td>`).join("")}</tr>`).join("")}</table>` : '<p class="muted">None.</p>'}
  <h3>Log</h3><pre>${r.log.map(esc).join("\n")}</pre>`;
}

async function runJob(id) { await api(`/jobs/${id}/run`, "POST"); show("jobs"); }
async function toggle(id, on) { await api(`/jobs/${id}/${on ? "disable" : "enable"}`, "POST"); show("jobs"); }
async function decide(id, what) { await api(`/approvals/${id}/${what}`, "POST"); show(current); }

let current = "overview";
async function show(name) {
  current = name;
  document.querySelectorAll(".dock button").forEach((b) => b.classList.toggle("active", b.dataset.app === name));
  $("#wtitle").textContent = document.querySelector(`[data-app=${name}] span`).textContent;
  $("#view").innerHTML = await views[name]();
  const s = await api("/stats");
  $("#badge").textContent = s.pending || "";
}
document.querySelectorAll(".dock button").forEach((b) => (b.onclick = () => show(b.dataset.app)));
setInterval(() => ($("#clock").textContent = new Date().toLocaleString()), 1000);
location.hash.length > 1 && views[location.hash.slice(1)] ? show(location.hash.slice(1)) : show("overview");
