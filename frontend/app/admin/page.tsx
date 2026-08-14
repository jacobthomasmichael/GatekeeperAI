"use client";

import { useEffect, useState } from "react";
import {
  approvalsApi,
  deploymentsApi,
  appsApi,
  adminApi,
  ssoApi,
  ApiError,
  type ApprovalStats,
  type Deployment,
  type AppSubmission,
  type User,
  type AuditLogEntry,
  type AuditLogPage,
  type SSOConfig,
  type SSOConfigCreate,
} from "@/lib/api";
import {
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Boxes,
  Layers,
  Users,
  ShieldCheck,
  UserPlus,
  ChevronLeft,
  ChevronRight,
  KeyRound,
  Trash2,
  Plus,
  CheckCircle2,
} from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import RiskBadge from "@/components/RiskBadge";

type Tab = "dashboard" | "users" | "audit" | "sso";

// ── Shared ────────────────────────────────────────────────────────────────────

const inputCls =
  "w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-signal-500";

const primaryBtn =
  "rounded-lg bg-signal-600 hover:bg-signal-700 px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-50";

const ROLE_LABELS: Record<string, string> = {
  ic: "IC",
  approver: "Approver",
  admin: "Admin",
};

const ROLE_COLORS: Record<string, string> = {
  ic: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300",
  approver: "bg-warn-50 dark:bg-warn-900/30 text-warn-800 dark:text-warn-300",
  admin: "bg-signal-50 dark:bg-signal-900/30 text-signal-700 dark:text-signal-300",
};

function RolePill({ role }: { role: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_COLORS[role] ?? ROLE_COLORS.ic}`}>
      {ROLE_LABELS[role] ?? role}
    </span>
  );
}

// ── Dashboard tab ─────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
  bg,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  bg: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
      <div className={`mb-3 inline-flex rounded-lg p-2 ${bg}`}>{icon}</div>
      <p className="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
      <p className="text-sm text-slate-400 dark:text-slate-500 mt-0.5">{label}</p>
    </div>
  );
}

function DashboardTab() {
  const [stats, setStats] = useState<ApprovalStats | null>(null);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [apps, setApps] = useState<AppSubmission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([approvalsApi.stats(), deploymentsApi.list(), appsApi.list()]).then(
      ([s, d, a]) => {
        setStats(s);
        setDeployments(d);
        setApps(a);
        setLoading(false);
      }
    );
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const running = deployments.filter((d) => d.status === "running").length;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xs font-semibold text-slate-400 dark:text-slate-400 mb-3 uppercase tracking-wider">
          Approvals
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Total"    value={stats.total}    icon={<Layers size={16} className="text-slate-500 dark:text-slate-400" />}       bg="bg-slate-100 dark:bg-slate-800" />
          <StatCard label="Pending"  value={stats.pending}  icon={<Clock size={16} className="text-warn-800 dark:text-warn-400" />}        bg="bg-warn-50 dark:bg-warn-900/30" />
          <StatCard label="Approved" value={stats.approved} icon={<CheckCircle size={16} className="text-good-600 dark:text-good-400" />} bg="bg-good-50 dark:bg-good-900/30" />
          <StatCard label="Rejected" value={stats.rejected} icon={<XCircle size={16} className="text-critical-600 dark:text-critical-400" />}          bg="bg-critical-50 dark:bg-critical-900/30" />
          <StatCard label="Overdue"  value={stats.overdue}  icon={<AlertTriangle size={16} className="text-orange-600 dark:text-orange-400" />} bg="bg-orange-50 dark:bg-orange-900/30" />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-slate-400 dark:text-slate-400 uppercase tracking-wider">
            Deployments
          </h2>
          <span className="text-xs text-slate-300 dark:text-slate-600">
            {running} running / {deployments.length} total
          </span>
        </div>
        {deployments.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center">
            <Boxes size={28} className="mx-auto text-slate-300 dark:text-slate-600 mb-2" />
            <p className="text-sm text-slate-400 dark:text-slate-500">No deployments yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {deployments.map((d) => (
              <div
                key={d.id}
                className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                    {d.container_name ?? d.id.slice(0, 8)}
                  </p>
                  {d.image_tag && (
                    <p className="text-xs text-slate-400 dark:text-slate-600 truncate">{d.image_tag}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge status={d.status} />
                  {d.public_url && d.status === "running" && (
                    <a
                      href={d.public_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-signal-600 dark:text-signal-400 hover:underline"
                    >
                      {d.public_url}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-slate-400 dark:text-slate-400 uppercase tracking-wider">
            All Apps
          </h2>
          <span className="text-xs text-slate-300 dark:text-slate-600">{apps.length} total</span>
        </div>
        <div className="space-y-2">
          {apps.map((app) => (
            <div
              key={app.id}
              className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{app.name}</p>
                <p className="text-xs text-slate-400 dark:text-slate-600 truncate">{app.description}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <StatusBadge status={app.status} />
                <RiskBadge tier={app.risk_tier} size="sm" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Users tab ─────────────────────────────────────────────────────────────────

function UsersTab() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ email: "", username: "", password: "", role: "ic" });
  const [resettingPasskeys, setResettingPasskeys] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    adminApi.listUsers().then((u) => { setUsers(u); setLoading(false); });
  };

  useEffect(load, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const payload = { ...form, password: form.password || undefined };
      const u = await adminApi.createUser(payload);
      setUsers((prev) => [...prev, u]);
      setForm({ email: "", username: "", password: "", role: "ic" });
      setShowCreate(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handleResetPasskeys = async (user: User) => {
    if (!confirm(`Remove all passkeys for ${user.email}? They will need to re-enroll.`)) return;
    setResettingPasskeys(user.id);
    try {
      await adminApi.resetPasskeys(user.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reset passkeys");
    } finally {
      setResettingPasskeys(null);
    }
  };

  const toggleActive = async (user: User) => {
    setUpdating(user.id);
    try {
      const updated = await adminApi.updateUser(user.id, { is_active: !user.is_active });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } finally {
      setUpdating(null);
    }
  };

  const changeRole = async (user: User, role: string) => {
    setUpdating(user.id);
    try {
      const updated = await adminApi.updateUser(user.id, { role });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } finally {
      setUpdating(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400 dark:text-slate-500">{users.length} user{users.length !== 1 ? "s" : ""}</p>
        <button onClick={() => setShowCreate((v) => !v)} className={primaryBtn}>
          <UserPlus size={14} className="inline mr-1.5 -mt-0.5" />
          {showCreate ? "Cancel" : "Add User"}
        </button>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 space-y-4"
        >
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">New User</h3>
          {error && <p className="text-xs text-critical-500">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 dark:text-slate-500 mb-1">Email</label>
              <input
                type="email"
                required
                className={inputCls}
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 dark:text-slate-500 mb-1">Username</label>
              <input
                type="text"
                required
                className={inputCls}
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 dark:text-slate-500 mb-1">
                Password <span className="text-slate-300 dark:text-slate-600 font-normal">(optional — user can enroll a passkey)</span>
              </label>
              <input
                type="password"
                className={inputCls}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 dark:text-slate-500 mb-1">Role</label>
              <select
                className={inputCls}
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              >
                <option value="ic">IC</option>
                <option value="approver">Approver</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={creating} className={primaryBtn}>
              {creating ? "Creating…" : "Create User"}
            </button>
          </div>
        </form>
      )}

      <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">User</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Role</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Joined</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
            {users.map((user) => (
              <tr key={user.id} className={updating === user.id ? "opacity-50" : ""}>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900 dark:text-white">{user.username}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">{user.email}</p>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={user.role}
                    disabled={updating === user.id}
                    onChange={(e) => changeRole(user, e.target.value)}
                    className="rounded-md border border-slate-200 dark:border-slate-700 bg-transparent px-2 py-1 text-xs text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-signal-500"
                  >
                    <option value="ic">IC</option>
                    <option value="approver">Approver</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400 dark:text-slate-500">
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => toggleActive(user)}
                    disabled={updating === user.id}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      user.is_active
                        ? "bg-good-50 dark:bg-good-900/30 text-good-700 dark:text-good-300 hover:bg-critical-50 dark:hover:bg-critical-900/30 hover:text-critical-600 dark:hover:text-critical-400"
                        : "bg-critical-50 dark:bg-critical-900/30 text-critical-600 dark:text-critical-400 hover:bg-good-50 dark:hover:bg-good-900/30 hover:text-good-700 dark:hover:text-good-300"
                    }`}
                  >
                    {user.is_active ? "Active" : "Disabled"}
                  </button>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleResetPasskeys(user)}
                    disabled={resettingPasskeys === user.id}
                    title="Remove all passkeys (account recovery)"
                    className="rounded-md px-2.5 py-1 text-xs text-slate-400 dark:text-slate-500 hover:text-orange-600 dark:hover:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/20 transition-colors disabled:opacity-50"
                  >
                    Reset passkeys
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Audit Log tab ─────────────────────────────────────────────────────────────

function AuditTab() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AuditLogPage | null>(null);
  const [loading, setLoading] = useState(true);

  const PAGE_SIZE = 50;

  useEffect(() => {
    setLoading(true);
    adminApi.listAuditLogs(page, PAGE_SIZE).then((d) => {
      setData(d);
      setLoading(false);
    });
  }, [page]);

  if (loading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400 dark:text-slate-500">{data.total} entries</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Time</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Actor</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Action</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">IP</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
            {data.items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                  No audit log entries yet
                </td>
              </tr>
            ) : (
              data.items.map((entry) => (
                <tr key={entry.id}>
                  <td className="px-4 py-2.5 text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                      {entry.actor_email ?? "—"}
                    </p>
                  </td>
                  <td className="px-4 py-2.5">
                    <code className="text-xs bg-slate-100 dark:bg-slate-800 rounded px-1.5 py-0.5 text-slate-700 dark:text-slate-300">
                      {entry.action}
                    </code>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-400 dark:text-slate-500 font-mono">
                    {entry.ip_address ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-400 dark:text-slate-500">
                    {entry.metadata
                      ? Object.entries(entry.metadata)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(", ")
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── SSO Tab ───────────────────────────────────────────────────────────────────

const ROLES = ["ic", "approver", "admin"] as const;
const ROLE_DISPLAY: Record<string, string> = { ic: "IC", approver: "Approver", admin: "Admin" };

function SSOTab() {
  const [config, setConfig] = useState<SSOConfig | null | undefined>(undefined);
  const [form, setForm] = useState<SSOConfigCreate>({
    provider_name: "",
    discovery_url: "",
    client_id: "",
    client_secret: "",
    group_claim_key: "groups",
    default_role: "ic",
    role_mappings: {},
    is_enabled: true,
  });
  const [newGroup, setNewGroup] = useState("");
  const [newGroupRole, setNewGroupRole] = useState<string>("ic");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; issuer?: string; error?: string } | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    ssoApi.getConfig()
      .then((c) => {
        setConfig(c);
        setForm({
          provider_name: c.provider_name,
          discovery_url: c.discovery_url,
          client_id: c.client_id,
          client_secret: "",
          group_claim_key: c.group_claim_key,
          default_role: c.default_role,
          role_mappings: c.role_mappings ?? {},
          is_enabled: c.is_enabled,
        });
      })
      .catch(() => setConfig(null));
  }, []);

  if (config === undefined) {
    return (
      <div className="flex h-48 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await ssoApi.testConfig({
        discovery_url: form.discovery_url,
        client_id: form.client_id,
        client_secret: form.client_secret,
      });
      setTestResult(r);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      if (config) {
        const updated = await ssoApi.updateConfig(form);
        setConfig(updated);
      } else {
        const created = await ssoApi.createConfig(form);
        setConfig(created);
        setForm((f) => ({ ...f, client_secret: "" }));
      }
      setSuccess("SSO configuration saved.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete SSO configuration? All SSO-only users will be unable to log in.")) return;
    setDeleting(true);
    try {
      await ssoApi.deleteConfig();
      setConfig(null);
      setForm({ provider_name: "", discovery_url: "", client_id: "", client_secret: "", group_claim_key: "groups", default_role: "ic", role_mappings: {}, is_enabled: true });
      setSuccess("SSO configuration deleted.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setDeleting(false);
    }
  };

  const addMapping = () => {
    if (!newGroup.trim()) return;
    setForm((f) => ({ ...f, role_mappings: { ...f.role_mappings, [newGroup.trim()]: newGroupRole } }));
    setNewGroup("");
    setNewGroupRole("ic");
  };

  const removeMapping = (group: string) => {
    setForm((f) => {
      const { [group]: _, ...rest } = f.role_mappings;
      return { ...f, role_mappings: rest };
    });
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-base font-semibold text-slate-900 dark:text-white">SSO / OIDC</h2>
        <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
          Connect an identity provider so users can sign in with SSO. Supports any OIDC-compliant provider (Okta, Azure AD, Google Workspace, Keycloak).
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-critical-200 dark:border-critical-700/40 bg-critical-50 dark:bg-critical-900/20 px-4 py-3 text-sm text-critical-600 dark:text-critical-400">
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-lg border border-good-200 dark:border-good-700/40 bg-good-50 dark:bg-good-900/20 px-4 py-3 text-sm text-good-600 dark:text-good-400">
          <CheckCircle2 size={15} />
          {success}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-5">
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">Provider</h3>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Provider Name</label>
              <input
                className={inputCls}
                placeholder="Okta"
                value={form.provider_name}
                onChange={(e) => setForm((f) => ({ ...f, provider_name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Group Claim Key</label>
              <input
                className={inputCls}
                placeholder="groups"
                value={form.group_claim_key}
                onChange={(e) => setForm((f) => ({ ...f, group_claim_key: e.target.value }))}
              />
              <p className="text-[11px] text-slate-400 dark:text-slate-500">
                Azure AD emits group Object IDs (GUIDs) by default, not display names.
              </p>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Discovery URL</label>
            <input
              className={inputCls}
              placeholder="https://your-idp.example.com/.well-known/openid-configuration"
              value={form.discovery_url}
              onChange={(e) => setForm((f) => ({ ...f, discovery_url: e.target.value }))}
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Client ID</label>
              <input
                className={inputCls}
                placeholder="0oa..."
                value={form.client_id}
                onChange={(e) => setForm((f) => ({ ...f, client_id: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Client Secret {config && <span className="text-slate-400 dark:text-slate-500 font-normal">(leave blank to keep existing)</span>}
              </label>
              <input
                type="password"
                className={inputCls}
                placeholder={config ? "••••••••" : "Client secret"}
                value={form.client_secret}
                onChange={(e) => setForm((f) => ({ ...f, client_secret: e.target.value }))}
                required={!config}
                autoComplete="new-password"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <button
              type="button"
              onClick={handleTest}
              disabled={testing || !form.discovery_url}
              className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
            >
              {testing ? "Testing…" : "Test connection"}
            </button>
            {testResult && (
              testResult.ok ? (
                <span className="flex items-center gap-1.5 text-xs text-good-600 dark:text-good-400">
                  <CheckCircle2 size={13} /> Connected — issuer: {testResult.issuer}
                </span>
              ) : (
                <span className="text-xs text-critical-500">{testResult.error}</span>
              )
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">Role Assignment</h3>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Default Role</label>
            <select
              className={inputCls}
              value={form.default_role}
              onChange={(e) => setForm((f) => ({ ...f, default_role: e.target.value }))}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{ROLE_DISPLAY[r]}</option>
              ))}
            </select>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">
              Role assigned when no group mapping matches. Google Workspace does not provide a standard groups claim, so all GWS users receive the default role.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Group → Role Mappings</label>
            {Object.entries(form.role_mappings).length === 0 ? (
              <p className="text-xs text-slate-400 dark:text-slate-500">No mappings — all SSO users get the default role.</p>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800 rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
                {Object.entries(form.role_mappings).map(([group, role]) => (
                  <div key={group} className="flex items-center justify-between px-3 py-2 bg-white dark:bg-slate-900">
                    <span className="text-xs text-slate-700 dark:text-slate-300 font-mono">{group}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 dark:text-slate-400">→ {ROLE_DISPLAY[role] ?? role}</span>
                      <button
                        type="button"
                        onClick={() => removeMapping(group)}
                        className="rounded p-1 text-slate-300 dark:text-slate-600 hover:text-critical-500 dark:hover:text-critical-400 transition-colors"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-2 items-center">
              <input
                type="text"
                placeholder="Group name or ID"
                value={newGroup}
                onChange={(e) => setNewGroup(e.target.value)}
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-signal-500 flex-1"
              />
              <select
                value={newGroupRole}
                onChange={(e) => setNewGroupRole(e.target.value)}
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-signal-500"
              >
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_DISPLAY[r]}</option>)}
              </select>
              <button
                type="button"
                onClick={addMapping}
                disabled={!newGroup.trim()}
                className="flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 px-2.5 py-1.5 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-40"
              >
                <Plus size={12} />
                Add
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_enabled}
              onChange={(e) => setForm((f) => ({ ...f, is_enabled: e.target.checked }))}
              className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-signal-600 focus:ring-signal-500"
            />
            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Enable SSO</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Uncheck to hide the SSO button without deleting the configuration.
              </p>
            </div>
          </label>
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className={primaryBtn}>
              {saving ? "Saving…" : config ? "Save changes" : "Enable SSO"}
            </button>
          </div>
          {config && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg border border-critical-200 dark:border-critical-800 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Delete SSO"}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

// ── Page root ─────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Dashboard",  icon: <Layers size={15} /> },
  { id: "users",     label: "Users",      icon: <Users size={15} /> },
  { id: "audit",     label: "Audit Log",  icon: <ShieldCheck size={15} /> },
  { id: "sso",       label: "SSO",        icon: <KeyRound size={15} /> },
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Admin</h1>
        <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">Platform management</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.id
                ? "border-signal-600 text-signal-600 dark:text-signal-400"
                : "border-transparent text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "users"     && <UsersTab />}
      {tab === "audit"     && <AuditTab />}
      {tab === "sso"       && <SSOTab />}
    </div>
  );
}
