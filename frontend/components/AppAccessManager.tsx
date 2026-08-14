"use client";

import { useEffect, useState } from "react";
import { appsApi, type AppUser } from "@/lib/api";
import { Users, Trash2, Plus, ChevronDown, ChevronUp, Crown } from "lucide-react";

const inputCls =
  "rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-signal-500";

const roleChipCls: Record<string, string> = {
  admin: "bg-critical-100 dark:bg-critical-900/30 text-critical-800 dark:text-critical-400",
  approver: "bg-warn-100 dark:bg-warn-900/30 text-warn-800 dark:text-warn-400",
  ic: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400",
};

interface Props {
  appId: string;
  isOwner: boolean;
}

export default function AppAccessManager({ appId, isOwner }: Props) {
  const [open, setOpen] = useState(false);
  const [users, setUsers] = useState<AppUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    appsApi.listUsers(appId).then((u) => { setUsers(u); setLoading(false); });
  }, [open, appId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const added = await appsApi.addUser(appId, email);
      setUsers((prev) => [...prev, added]);
      setEmail("");
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to grant access");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (userId: string) => {
    setDeleting(userId);
    try {
      await appsApi.removeUser(appId, userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="mt-3 border-t border-slate-100 dark:border-slate-800 pt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs font-medium text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
      >
        <Users size={13} />
        App Access
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        {users.length > 0 && !open && (
          <span className="ml-1 rounded-full bg-signal-100 dark:bg-signal-900/40 px-1.5 py-0.5 text-signal-600 dark:text-signal-400">
            {users.length}
          </span>
        )}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
              Loading…
            </div>
          ) : (
            <>
              <div className="rounded-lg border border-slate-100 dark:border-slate-800 overflow-hidden">
                {/* Owner row — always shown, not removable */}
                <div className="flex items-center justify-between px-3 py-2 gap-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
                  <div className="flex items-center gap-2 min-w-0">
                    <Crown size={12} className="text-warn-600 shrink-0" />
                    <span className="text-xs text-slate-500 dark:text-slate-400">Owner</span>
                  </div>
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    {isOwner ? "You" : "App owner"}
                  </span>
                </div>

                {users.length === 0 && (
                  <div className="px-3 py-2 text-xs text-slate-400 dark:text-slate-500">
                    No one else has access yet.
                  </div>
                )}

                {users.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between px-3 py-2 gap-3 border-b last:border-b-0 border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs text-slate-700 dark:text-slate-300 truncate">
                        {u.email}
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${roleChipCls[u.role] ?? roleChipCls.ic}`}
                      >
                        {u.role}
                      </span>
                    </div>
                    {isOwner && (
                      <button
                        onClick={() => handleRemove(u.id)}
                        disabled={deleting === u.id}
                        className="rounded p-1 text-slate-300 dark:text-slate-600 hover:text-critical-500 dark:hover:text-critical-400 disabled:opacity-40 transition-colors shrink-0"
                        title="Remove access"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {isOwner && (
                showForm ? (
                  <form onSubmit={handleAdd} className="space-y-2">
                    {error && <p className="text-xs text-critical-500">{error}</p>}
                    <div className="flex gap-2">
                      <input
                        type="email"
                        placeholder="colleague@company.com"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className={`${inputCls} flex-1`}
                      />
                    </div>
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => { setShowForm(false); setEmail(""); setError(""); }}
                        className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={saving}
                        className="rounded-lg bg-signal-600 hover:bg-signal-700 px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50"
                      >
                        {saving ? "Granting…" : "Grant Access"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-1.5 text-xs text-signal-600 dark:text-signal-400 hover:text-signal-800 dark:hover:text-signal-200 transition-colors"
                  >
                    <Plus size={13} />
                    Add person
                  </button>
                )
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
