const API = "/api/v1";

async function postJson(path: string, body: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export async function login(username: string, password: string) {
  return postJson("/auth/login", { username, password });
}

export async function createResearchRun(input: {
  keyword: string;
  research_prompt?: string;
  language?: string;
  period_days?: number;
}) {
  return postJson("/research-runs", {
    keyword: input.keyword,
    research_prompt: input.research_prompt || "",
    language: input.language || "id-ID",
    period_days: input.period_days || 7,
  });
}

export async function startResearchRun(id: string) {
  return postJson(`/research-runs/${id}/start`, {});
}

export async function approveCandidate(id: string) {
  return postJson(`/candidates/${id}/approve`, {});
}

export async function rejectCandidate(id: string) {
  return postJson(`/candidates/${id}/reject`, {});
}

export async function createRenderJob(candidateId: string, profileName: string) {
  return postJson(
    `/candidates/${candidateId}/render-jobs?profile_name=${encodeURIComponent(profileName)}`,
    {}
  );
}

export async function listProfiles() {
  const res = await fetch(`${API}/render-profiles`, { credentials: "include" });
  return res.json();
}

export async function getRun(id: string) {
  const res = await fetch(`${API}/research-runs/${id}`, { credentials: "include" });
  return res.json();
}

export async function getCandidates(id: string) {
  const res = await fetch(`${API}/research-runs/${id}/candidates`, {
    credentials: "include",
  });
  return res.json();
}

export async function listRuns() {
  const res = await fetch(`${API}/research-runs`, { credentials: "include" });
  if (!res.ok) return [];
  return res.json();
}

export async function listJobs(statusFilter?: string) {
  const q = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  const res = await fetch(`${API}/render-jobs${q}`, { credentials: "include" });
  if (!res.ok) return [];
  return res.json();
}

export async function getJob(id: string) {
  const res = await fetch(`${API}/render-jobs/${id}`, { credentials: "include" });
  if (!res.ok) return null;
  return res.json();
}

export async function getJobEvents(id: string) {
  const res = await fetch(`${API}/render-jobs/${id}/events`, { credentials: "include" });
  if (!res.ok) return [];
  return res.json();
}

export async function getJobOutputs(id: string) {
  const res = await fetch(`${API}/render-jobs/${id}/outputs`, { credentials: "include" });
  if (!res.ok) return [];
  return res.json();
}

export async function cancelJob(id: string) {
  return postJson(`/render-jobs/${id}/cancel`, {});
}

