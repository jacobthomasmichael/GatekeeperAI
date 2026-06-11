const BASE = process.env.NEXT_PUBLIC_API_URL!;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("gka_token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail = text;
    try {
      detail = JSON.parse(text)?.detail ?? text;
    } catch {}
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// ── Types ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  role: "ic" | "approver" | "admin";
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RejectionFeedback {
  decision: string;
  comment: string;
  decided_at: string;
}

export interface AppSubmission {
  id: string;
  name: string;
  description: string;
  repo_path: string;
  repo_url: string;
  detected_type: string | null;
  status: string;
  risk_tier: string | null;
  submitter_id: string;
  commit_sha: string | null;
  created_at: string;
  rejection: RejectionFeedback | null;
}

export interface ScanResult {
  id: string;
  scanner_name: string;
  status: string;
  severity: string;
  findings: Record<string, unknown>;
  duration_ms: number;
}

export interface Scan {
  id: string;
  submission_id: string;
  commit_sha: string | null;
  status: string;
  risk_tier: string | null;
  risk_score: number | null;
  started_at: string | null;
  completed_at: string | null;
  scan_results: ScanResult[];
}

export interface ApprovalDetail {
  id: string;
  scan_id: string;
  approver_id: string | null;
  decision: string | null;
  comment: string | null;
  sla_deadline: string;
  decided_at: string | null;
  created_at: string;
  app_name: string;
  app_description: string;
  submitter_id: string;
  commit_sha: string;
  risk_tier: string;
  risk_score: number;
  scan_results: ScanResult[];
}

export interface ApprovalStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  overdue: number;
}

export interface Deployment {
  id: string;
  submission_id: string;
  scan_id: string;
  container_id: string | null;
  container_name: string | null;
  image_tag: string | null;
  status: string;
  internal_port: number | null;
  external_port: number | null;
  public_url: string | null;
  started_at: string | null;
  stopped_at: string | null;
  created_at: string;
}

// ── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }),
  register: (email: string, username: string, password: string) =>
    api.post<User>("/auth/register", { email, username, password }),
  me: () => api.get<User>("/auth/me"),
};

// ── Apps API ─────────────────────────────────────────────────────────────────

export const appsApi = {
  list: () => api.get<AppSubmission[]>("/apps/"),
  get: (id: string) => api.get<AppSubmission>(`/apps/${id}`),
  create: (name: string, description: string) =>
    api.post<AppSubmission>("/apps/", { name, description }),
  cloneUrl: (id: string) =>
    api.get<{ clone_url: string; repo_path: string }>(`/apps/${id}/clone-url`),
  delete: (id: string) => api.delete(`/apps/${id}`),
};

// ── Scans API ─────────────────────────────────────────────────────────────────

export const scansApi = {
  get: (scanId: string) => api.get<Scan>(`/scans/${scanId}`),
  listForApp: (appId: string) => api.get<Scan[]>(`/scans/app/${appId}`),
  streamUrl: (scanId: string) => `${BASE}/scans/${scanId}/stream`,
};

// ── Approvals API ─────────────────────────────────────────────────────────────

export const approvalsApi = {
  list: (pendingOnly = true) =>
    api.get<ApprovalDetail[]>(`/approvals/?pending_only=${pendingOnly}`),
  get: (id: string) => api.get<ApprovalDetail>(`/approvals/${id}`),
  decide: (id: string, decision: string, comment: string) =>
    api.post(`/approvals/${id}/decide`, { decision, comment }),
  stats: () => api.get<ApprovalStats>("/approvals/stats"),
};

// ── Deployments API ───────────────────────────────────────────────────────────

export const deploymentsApi = {
  list: () => api.get<Deployment[]>("/deployments/"),
  getForApp: (submissionId: string) =>
    api.get<Deployment>(`/deployments/app/${submissionId}`),
  status: (deploymentId: string) =>
    api.get<{ status: string; public_url: string | null }>(
      `/deployments/${deploymentId}/status`
    ),
  logs: (deploymentId: string, tail = 200) =>
    api.get<{ logs: string }>(`/deployments/${deploymentId}/logs?tail=${tail}`),
};
