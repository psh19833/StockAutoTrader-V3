// Dashboard API client — fetches SAT3 backend status
const API_BASE = "http://localhost:8000";

export async function fetchDashboardSummary() {
  const res = await fetch(`${API_BASE}/api/dashboard/summary`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchSystemStatus() {
  const res = await fetch(`${API_BASE}/api/dashboard/system`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchSessionStatus() {
  const res = await fetch(`${API_BASE}/api/dashboard/session`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchWebSocketStatus() {
  const res = await fetch(`${API_BASE}/api/dashboard/ws-status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchCandidates() {
  const res = await fetch(`${API_BASE}/api/dashboard/candidates`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchRiskDecisions() {
  const res = await fetch(`${API_BASE}/api/dashboard/risk-decisions`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
