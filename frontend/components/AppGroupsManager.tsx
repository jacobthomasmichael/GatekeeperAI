"use client";

import { useEffect, useState } from "react";
import { appsApi } from "@/lib/api";
import { Tag, Trash2, Plus, ChevronDown, ChevronUp } from "lucide-react";

const inputCls =
  "rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-signal-500";

interface Props {
  appId: string;
  isOwner: boolean;
  ssoEnabled: boolean;
}

export default function AppGroupsManager({ appId, isOwner, ssoEnabled }: Props) {
  const [open, setOpen] = useState(false);
  const [groups, setGroups] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState("");

  if (!ssoEnabled) return null;

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    appsApi.listGroups(appId).then((g) => { setGroups(g); setLoading(false); });
  }, [open, appId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await appsApi.addGroup(appId, groupName.trim());
      setGroups((prev) => [...prev, groupName.trim()]);
      setGroupName("");
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add group");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (group: string) => {
    setRemoving(group);
    try {
      await appsApi.removeGroup(appId, group);
      setGroups((prev) => prev.filter((g) => g !== group));
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="mt-3 border-t border-slate-100 dark:border-slate-800 pt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs font-medium text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
      >
        <Tag size={13} />
        Group Access
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        {groups.length > 0 && !open && (
          <span className="ml-1 rounded-full bg-violet-100 dark:bg-violet-900/40 px-1.5 py-0.5 text-violet-600 dark:text-violet-400">
            {groups.length}
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
              {groups.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {groups.map((g) => (
                    <span
                      key={g}
                      className="inline-flex items-center gap-1.5 rounded-full bg-violet-100 dark:bg-violet-900/30 px-2.5 py-1 text-xs font-medium text-violet-700 dark:text-violet-300"
                    >
                      {g}
                      {isOwner && (
                        <button
                          onClick={() => handleRemove(g)}
                          disabled={removing === g}
                          className="rounded-full text-violet-400 dark:text-violet-500 hover:text-critical-500 dark:hover:text-critical-400 disabled:opacity-40 transition-colors"
                          title="Remove group"
                        >
                          <Trash2 size={11} />
                        </button>
                      )}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  No groups have access yet.
                </p>
              )}

              {isOwner && (
                showForm ? (
                  <form onSubmit={handleAdd} className="space-y-2">
                    {error && <p className="text-xs text-critical-500">{error}</p>}
                    <input
                      type="text"
                      placeholder="Group name or ID from your identity provider"
                      required
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                      className={`${inputCls} w-full`}
                      title="Use the exact group name or Object ID as it appears in your identity provider (e.g. Azure AD Object IDs are GUIDs by default)."
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => { setShowForm(false); setGroupName(""); setError(""); }}
                        className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={saving}
                        className="rounded-lg bg-violet-600 hover:bg-violet-700 px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50"
                      >
                        {saving ? "Adding…" : "Add Group"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-1.5 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-800 dark:hover:text-violet-200 transition-colors"
                  >
                    <Plus size={13} />
                    Add group
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
