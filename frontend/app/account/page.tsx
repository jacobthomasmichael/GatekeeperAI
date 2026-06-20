"use client";

import { useEffect, useState } from "react";
import { ApiError, passkeyApi, type PasskeyEntry } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Fingerprint, Trash2, PlusCircle, Loader2, Monitor, Smartphone } from "lucide-react";

function DeviceIcon({ label }: { label: string | null }) {
  const lower = (label ?? "").toLowerCase();
  if (lower.includes("phone") || lower.includes("iphone") || lower.includes("android")) {
    return <Smartphone size={14} className="shrink-0 text-gray-400 dark:text-slate-500" />;
  }
  return <Monitor size={14} className="shrink-0 text-gray-400 dark:text-slate-500" />;
}

export default function AccountPage() {
  const { user } = useAuth();
  const [passkeys, setPasskeys] = useState<PasskeyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [deviceLabel, setDeviceLabel] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = () => {
    passkeyApi.list().then((pks) => { setPasskeys(pks); setLoading(false); });
  };

  useEffect(load, []);

  async function handleEnroll() {
    setError("");
    setSuccess("");
    setEnrolling(true);
    try {
      const { startRegistration } = await import("@simplewebauthn/browser");
      const options = await passkeyApi.registerBegin(deviceLabel || undefined);
      const credential = await startRegistration({ optionsJSON: options as never });
      const pk = await passkeyApi.registerComplete(credential, deviceLabel || undefined);
      setPasskeys((prev) => [...prev, pk]);
      setDeviceLabel("");
      setSuccess("Passkey enrolled successfully.");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error && err.name === "NotAllowedError") {
        setError("Passkey prompt was dismissed.");
      } else {
        setError("Enrollment failed. Please try again.");
      }
    } finally {
      setEnrolling(false);
    }
  }

  async function handleRemove(passkeyId: string) {
    setRemoving(passkeyId);
    setError("");
    setSuccess("");
    try {
      await passkeyApi.delete(passkeyId);
      setPasskeys((prev) => prev.filter((pk) => pk.id !== passkeyId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to remove passkey");
    } finally {
      setRemoving(null);
    }
  }

  const inputCls =
    "rounded-md border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Account</h1>
        <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">{user?.email}</p>
      </div>

      {/* Passkey management */}
      <section className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 divide-y divide-gray-100 dark:divide-slate-800">
        <div className="p-5">
          <div className="flex items-center gap-2 mb-1">
            <Fingerprint size={18} className="text-indigo-500" />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Passkeys</h2>
          </div>
          <p className="text-xs text-gray-400 dark:text-slate-500">
            Sign in with Face ID, Touch ID, or Windows Hello — no password needed.
          </p>
        </div>

        {/* Feedback */}
        {error && (
          <div className="px-5 py-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20">
            {error}
          </div>
        )}
        {success && (
          <div className="px-5 py-3 text-sm text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20">
            {success}
          </div>
        )}

        {/* Existing passkeys */}
        {loading ? (
          <div className="flex items-center justify-center h-20">
            <Loader2 size={18} className="animate-spin text-gray-300 dark:text-slate-600" />
          </div>
        ) : passkeys.length === 0 ? (
          <div className="px-5 py-6 text-center text-sm text-gray-400 dark:text-slate-500">
            No passkeys enrolled yet.
          </div>
        ) : (
          <ul>
            {passkeys.map((pk) => (
              <li key={pk.id} className="flex items-center justify-between px-5 py-3 gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <DeviceIcon label={pk.device_label} />
                  <div className="min-w-0">
                    <p className="text-sm text-gray-800 dark:text-slate-200 truncate">
                      {pk.device_label ?? "Unnamed device"}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-slate-500">
                      Added {new Date(pk.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleRemove(pk.id)}
                  disabled={removing === pk.id}
                  className="shrink-0 flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-gray-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                >
                  {removing === pk.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Enroll new passkey */}
        <div className="p-5 space-y-3">
          <p className="text-xs font-medium text-gray-500 dark:text-slate-400">Add this device</p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Device label (e.g. MacBook Touch ID)"
              value={deviceLabel}
              onChange={(e) => setDeviceLabel(e.target.value)}
              className={`flex-1 ${inputCls}`}
            />
            <button
              onClick={handleEnroll}
              disabled={enrolling}
              className="flex items-center gap-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {enrolling ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <PlusCircle size={14} />
              )}
              {enrolling ? "Waiting…" : "Add passkey"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
