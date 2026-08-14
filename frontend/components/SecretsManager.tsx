"use client";

import { useEffect, useState } from "react";
import { secretsApi, type SecretKey } from "@/lib/api";
import { KeyRound, Trash2, Plus, Eye, EyeOff, ChevronDown, ChevronUp } from "lucide-react";

const inputCls =
  "rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-signal-500";

interface Props {
  appId: string;
}

export default function SecretsManager({ appId }: Props) {
  const [open, setOpen] = useState(false);
  const [secrets, setSecrets] = useState<SecretKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [value, setValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    secretsApi.list(appId).then((s) => { setSecrets(s); setLoading(false); });
  }, [open, appId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const created = await secretsApi.create(appId, keyName, value);
      setSecrets((prev) => {
        const filtered = prev.filter((s) => s.key_name !== created.key_name);
        return [...filtered, created];
      });
      setKeyName("");
      setValue("");
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save secret");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (name: string) => {
    setDeleting(name);
    try {
      await secretsApi.delete(appId, name);
      setSecrets((prev) => prev.filter((s) => s.key_name !== name));
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
        <KeyRound size={13} />
        Environment Secrets
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        {secrets.length > 0 && !open && (
          <span className="ml-1 rounded-full bg-signal-100 dark:bg-signal-900/40 px-1.5 py-0.5 text-signal-600 dark:text-signal-400">
            {secrets.length}
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
              {secrets.length === 0 && !showForm && (
                <p className="text-xs text-slate-400 dark:text-slate-500">No secrets set.</p>
              )}

              {secrets.length > 0 && (
                <div className="rounded-lg border border-slate-100 dark:border-slate-800 overflow-hidden">
                  {secrets.map((s) => (
                    <div
                      key={s.key_name}
                      className="flex items-center justify-between px-3 py-2 gap-3 border-b last:border-b-0 border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <KeyRound size={12} className="text-slate-400 dark:text-slate-500 shrink-0" />
                        <code className="text-xs font-mono text-slate-700 dark:text-slate-300 truncate">
                          {s.key_name}
                        </code>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-slate-300 dark:text-slate-600 font-mono tracking-widest">
                          ••••••••
                        </span>
                        <button
                          onClick={() => handleDelete(s.key_name)}
                          disabled={deleting === s.key_name}
                          className="rounded p-1 text-slate-300 dark:text-slate-600 hover:text-critical-500 dark:hover:text-critical-400 disabled:opacity-40 transition-colors"
                          title="Delete secret"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {showForm ? (
                <form onSubmit={handleAdd} className="space-y-2">
                  {error && <p className="text-xs text-critical-500">{error}</p>}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="KEY_NAME"
                      required
                      value={keyName}
                      onChange={(e) => setKeyName(e.target.value.toUpperCase())}
                      className={`${inputCls} flex-1 font-mono uppercase`}
                    />
                    <div className="relative flex-1">
                      <input
                        type={showValue ? "text" : "password"}
                        placeholder="value"
                        required
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        className={`${inputCls} w-full pr-9`}
                      />
                      <button
                        type="button"
                        onClick={() => setShowValue((v) => !v)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400"
                      >
                        {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => { setShowForm(false); setKeyName(""); setValue(""); setError(""); }}
                      className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={saving}
                      className="rounded-lg bg-signal-600 hover:bg-signal-700 px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50"
                    >
                      {saving ? "Saving…" : "Save Secret"}
                    </button>
                  </div>
                </form>
              ) : (
                <button
                  onClick={() => setShowForm(true)}
                  className="flex items-center gap-1.5 text-xs text-signal-600 dark:text-signal-400 hover:text-signal-800 dark:hover:text-signal-200 transition-colors"
                >
                  <Plus size={13} />
                  Add secret
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
