const state = { token: localStorage.getItem("sentinel_access_token"), api: localStorage.getItem("sentinel_api") || "http://localhost:8000", file: null };
const $ = (id) => document.getElementById(id);
const nowParts = () => { const d = new Date(); return { hour: d.getHours(), minute: d.getMinutes(), second: d.getSeconds() }; };
const api = (path, options = {}) => fetch(`${state.api}${path}`, { ...options, headers: { "Content-Type": "application/json", Authorization: `Bearer ${state.token}`, ...(options.headers || {}) } });

function showDashboard() { $("login-view").hidden = true; $("dashboard-view").hidden = false; loadDashboard(); }
function showLogin() { $("login-view").hidden = false; $("dashboard-view").hidden = true; }
function setResult(message, success = true) { $("ingest-result").textContent = message; $("ingest-result").className = `result ${success ? "success" : "failure"}`; }
function readTime() { const value = $("time").value || "00:00:00"; const [hour, minute, second] = value.split(":").map(Number); return { hour, minute, second: second || 0 }; }
function toPayload(line, fallbackComponent = "SecurityService") {
  const isObject = line !== null && typeof line === "object";
  const rawValue = isObject ? (line.raw_log || line.content || line.message || "") : String(line);
  const timestamp = rawValue.match(/\b(?:19|20)\d{2}[-/]\d{2}[-/]\d{2}[ T](\d{2}):(\d{2}):(\d{2})/);
  const time = timestamp ? { hour: Number(timestamp[1]), minute: Number(timestamp[2]), second: Number(timestamp[3]) } : nowParts();
  return { content: rawValue.trim(), component: String(isObject && line.component || fallbackComponent), ...time, time_gap: Number(isObject && line.time_gap || 0), pid_freq: Number(isObject && line.pid_freq || 1), raw_log: rawValue.trim() };
}
function parseCsv(text) {
  const rows = []; let row = []; let value = ""; let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]; const next = text[i + 1];
    if (char === '"' && quoted && next === '"') { value += '"'; i += 1; }
    else if (char === '"') quoted = !quoted;
    else if (char === "," && !quoted) { row.push(value); value = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) { if (char === "\r" && next === "\n") i += 1; row.push(value); if (row.some((cell) => cell.trim())) rows.push(row); row = []; value = ""; }
    else value += char;
  }
  if (value || row.length) { row.push(value); rows.push(row); }
  if (rows.length < 2) return [];
  const headers = rows.shift().map((x) => x.trim().toLowerCase());
  return rows.map((values) => Object.fromEntries(headers.map((header, i) => [header, values[i] || ""])));
}
async function uploadFile() {
  if (!state.file) return;
  try {
    const text = await state.file.text(); let entries;
    if (state.file.name.toLowerCase().endsWith(".json") || state.file.name.toLowerCase().endsWith(".jsonl")) {
      entries = state.file.name.toLowerCase().endsWith(".jsonl") ? text.trim().split(/\r?\n/).map((x) => JSON.parse(x)) : JSON.parse(text);
      if (!Array.isArray(entries)) entries = [entries];
    } else if (state.file.name.toLowerCase().endsWith(".csv")) entries = parseCsv(text);
    else entries = text.split(/\r?\n/).filter(Boolean);
    entries = entries.slice(0, 100).map(toPayload);
    if (!entries.length) throw new Error("The selected file contains no log entries.");
    const response = await api("/logs/batch", { method: "POST", body: JSON.stringify({ logs: entries }) });
    if (!response.ok) throw new Error(`Upload failed (${response.status}).`);
    setResult(`${entries.length} log${entries.length === 1 ? "" : "s"} submitted for analysis.`);
    await loadDashboard();
  } catch (error) { setResult(error.message, false); }
}
async function submitSingle(event) {
  event.preventDefault();
  const payload = { content: $("content").value, component: $("component").value, ...readTime(), raw_log: $("raw-log").value || $("content").value };
  try {
    const response = await api("/logs/ingest?wait=false", { method: "POST", body: JSON.stringify(payload) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not enqueue log.");
    setResult(`Queued as ticket #${data.queue_number}. Processing will appear in the dashboard shortly.`);
    $("single-form").reset(); $("component").value = "SecurityService"; await loadDashboard();
  } catch (error) { setResult(error.message, false); }
}
async function loadDashboard() {
  try {
    const [summaryResponse, logsResponse] = await Promise.all([api("/logs/summary"), api("/logs?limit=20")]);
    if (summaryResponse.status === 401 || logsResponse.status === 401) { localStorage.removeItem("sentinel_access_token"); state.token = null; showLogin(); return; }
    if (!summaryResponse.ok || !logsResponse.ok) throw new Error("Dashboard telemetry is unavailable.");
    const summary = await summaryResponse.json(); const logs = await logsResponse.json();
    $("metric-total").textContent = summary.total_analyzed; $("metric-safe").textContent = summary.safe; $("metric-warn").textContent = summary.warn; $("metric-pending").textContent = summary.pending; $("metric-processing").textContent = `${summary.processing} processing`; $("last-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    $("activity").innerHTML = logs.length ? logs.map((log) => `<div class="activity-row"><span class="pill ${log.prediction === "INFO" ? "safe" : ["WARN","ERROR"].includes(log.prediction) ? "warn" : "other"}">${escapeHtml(log.prediction)}</span><span class="log-line" title="${escapeHtml(log.content)}">${escapeHtml(log.content)}</span><small>${escapeHtml(log.status)}</small>${log.has_explainability ? `<button class="ghost explanation-button" data-log-id="${log.id}" type="button">Read explanation</button>` : ""}</div>`).join("") : '<p class="muted">No logs loaded yet.</p>';
    document.querySelectorAll(".explanation-button").forEach((button) => button.addEventListener("click", () => loadExplanation(button.dataset.logId)));
  } catch (error) { $("last-updated").textContent = error.message; }
}
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char])); }
async function loadExplanation(logId) {
  const panel = $("explanation-panel");
  const content = $("explanation-content");
  panel.hidden = false;
  content.innerHTML = '<p class="muted">Loading explanation...</p>';
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const [explanationResponse, logResponse] = await Promise.all([
      api(`/logs/explainable/${encodeURIComponent(logId)}`),
      api(`/logs/${encodeURIComponent(logId)}`),
    ]);
    const data = await explanationResponse.json();
    const log = await logResponse.json();
    if (!explanationResponse.ok) throw new Error(data.detail || "Could not load explanation.");
    if (!logResponse.ok) throw new Error(log.detail || "Could not load raw log.");
    content.innerHTML = `
      <div class="explanation-grid">
        <div class="explanation-field"><span>Threat level</span><strong>${escapeHtml(data.threat_level)}</strong></div>
        <div class="explanation-field"><span>Attack type</span><strong>${escapeHtml(data.attack_type || "Unknown")}</strong></div>
        <div class="explanation-field"><span>Confidence</span><strong>${Math.round(Number(data.confidence_score || 0) * 100)}%</strong></div>
        <div class="explanation-field"><span>Model</span><strong>${escapeHtml(data.llm_model)}</strong></div>
        <div class="explanation-field"><span>Queue number</span><strong>#${escapeHtml(data.queue_number)}</strong></div>
        <div class="explanation-field"><span>MITRE ATT&CK</span><strong>${escapeHtml((data.mitre_attack_ids || []).join(", ") || "Not mapped")}</strong></div>
      </div>
      <div class="stack">
        <div><p class="eyebrow">DETECTION SUMMARY</p><p class="explanation-copy">${escapeHtml(data.detection_summary)}</p></div>
        <div><p class="eyebrow">EXPLANATION</p><p class="explanation-copy">${escapeHtml(data.explanation)}</p></div>
        <div><p class="eyebrow">RECOMMENDED ACTION</p><p class="explanation-copy">${escapeHtml(data.recommended_action || "No recommendation provided.")}</p></div>
        <div><p class="eyebrow">RAW LOG</p><p class="raw-log">${escapeHtml(log.raw_log || log.content)}</p></div>
      </div>`;
  } catch (error) {
    content.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); state.api = $("api-base").value.replace(/\/$/, ""); localStorage.setItem("sentinel_api", state.api);
  $("login-error").textContent = "";
  try { const response = await fetch(`${state.api}/api/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: $("email").value, password: $("password").value, identity_type: "organization" }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Login failed."); state.token = data.access_token; localStorage.setItem("sentinel_access_token", state.token); showDashboard(); } catch (error) { $("login-error").textContent = error.message; }
});
$("logout").addEventListener("click", () => { localStorage.removeItem("sentinel_access_token"); state.token = null; showLogin(); });
$("refresh").addEventListener("click", loadDashboard);
$("close-explanation").addEventListener("click", () => { $("explanation-panel").hidden = true; });
$("single-form").addEventListener("submit", submitSingle);
$("log-file").addEventListener("change", (event) => { state.file = event.target.files[0]; $("file-name").textContent = state.file ? `${state.file.name} selected` : "No file selected"; $("upload-file").disabled = !state.file; });
$("upload-file").addEventListener("click", uploadFile);
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => { document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab)); $("single-form").hidden = tab.dataset.tab !== "single"; $("file-panel").hidden = tab.dataset.tab !== "file"; }));
setInterval(() => { if (state.token) loadDashboard(); }, 5000);
if (state.token) showDashboard();
