// Dashboard API client — SAT3 backend status
const API_BASE = "http://localhost:8000";

export async function fetchDashboardSummary() {
  const res = await fetch(`${API_BASE}/api/dashboard/summary`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchTelegramStatus() {
  const res = await fetch(`${API_BASE}/api/dashboard/telegram-status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchKisAccount() {
  const res = await fetch(`${API_BASE}/api/dashboard/kis-account`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchDailySummary(date = "") {
  const params = date ? `?date=${date}` : "";
  const res = await fetch(`${API_BASE}/api/dashboard/daily-summary${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchStrategyBreakdown(date = "") {
  const params = date ? `?date=${date}` : "";
  const res = await fetch(`${API_BASE}/api/dashboard/strategy-breakdown${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchLogs(date = "", category = "system", maxLines = 100) {
  const params = `?date=${date}&category=${category}&max_lines=${maxLines}`;
  const res = await fetch(`${API_BASE}/api/dashboard/logs${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchLogDates() {
  const res = await fetch(`${API_BASE}/api/dashboard/log-dates`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuditTimeline(limit = 50) {
  const res = await fetch(`${API_BASE}/api/dashboard/audit?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuditEventDetail(eventId) {
  const res = await fetch(`${API_BASE}/api/dashboard/audit/${eventId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
