const BASE = process.env.NEXT_PUBLIC_API_URL!;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// ── Token storage ─────────────────────────────────────────────────────────────

const TOKEN_KEY = "gka_token";
const REFRESH_KEY = "gka_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function storeTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// Emitted when a refresh attempt fails — auth context listens and logs the user out.
export const AUTH_EXPIRED_EVENT = "gka:auth-expired";

// ── Refresh lock ──────────────────────────────────────────────────────────────

let refreshing: Promise<string | null> | null = null;

async function attemptRefresh(): Promise<string | null> {
  if (refreshing) return refreshing;

  refreshing = (async () => {
    const rt = typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
    if (!rt) return null;
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return null;
      const data: { access_token: string; refresh_token: string } = await res.json();
      storeTokens(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

// ── Core fetch ────────────────────────────────────────────────────────────────

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const doFetch = (accessToken: string | null) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    return fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await doFetch(getAccessToken());

  if (res.status === 401) {
    const newToken = await attemptRefresh();
    if (newToken) {
      res = await doFetch(newToken);
    } else {
      clearTokens();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
      }
      throw new ApiError(401, "Session expired. Please log in again.");
    }
  }

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
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
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
  me: () => api.get<User>("/auth/me"),
};

// ── Apps API ─────────────────────────────────────────────────────────────────

export const appsApi = {
  list: () => api.get<AppSubmission[]>("/apps/"),
  get: (id: string) => api.get<AppSubmission>(`/apps/${id}`),
  create: (name: string, description: string) =>
    api.post<AppSubmission>("/apps/", { name, description }),
  cloneUrl: (id: string) =>
    api.get<{ clone_url: string; ssh_clone_url: string; repo_path: string }>(`/apps/${id}/clone-url`),
  uploadZip: async (id: string, file: File): Promise<{ scan_id: string; commit_sha: string }> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/apps/${id}/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      let detail = text;
      try { detail = JSON.parse(text)?.detail ?? text; } catch {}
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },
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
  get: (deploymentId: string) => api.get<Deployment>(`/deployments/${deploymentId}`),
  getForApp: (submissionId: string) =>
    api.get<Deployment>(`/deployments/app/${submissionId}`),
  status: (deploymentId: string) =>
    api.get<{ status: string; public_url: string | null }>(
      `/deployments/${deploymentId}/status`
    ),
  logs: (deploymentId: string, tail = 200) =>
    api.get<{ logs: string }>(`/deployments/${deploymentId}/logs?tail=${tail}`),
  stop: (deploymentId: string) =>
    api.post<Deployment>(`/deployments/${deploymentId}/stop`),
  start: (deploymentId: string) =>
    api.post<Deployment>(`/deployments/${deploymentId}/start`),
};

// ── Secrets API ───────────────────────────────────────────────────────────────

export interface SecretKey {
  key_name: string;
  submission_id: string;
}

export const secretsApi = {
  list: (appId: string) => api.get<SecretKey[]>(`/apps/${appId}/secrets/`),
  create: (appId: string, key_name: string, value: string) =>
    api.post<SecretKey>(`/apps/${appId}/secrets/`, { key_name, value }),
  delete: (appId: string, keyName: string) =>
    api.delete<void>(`/apps/${appId}/secrets/${keyName}`),
};

// ── Admin API ─────────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: number;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogPage {
  total: number;
  page: number;
  page_size: number;
  items: AuditLogEntry[];
}

export const adminApi = {
  listUsers: () => api.get<User[]>("/admin/users"),
  createUser: (payload: { email: string; username: string; password: string; role: string }) =>
    api.post<User>("/admin/users", payload),
  updateUser: (id: string, patch: { role?: string; is_active?: boolean }) =>
    api.patch<User>(`/admin/users/${id}`, patch),
  listAuditLogs: (page = 1, pageSize = 50) =>
    api.get<AuditLogPage>(`/admin/audit-logs?page=${page}&page_size=${pageSize}`),
};
