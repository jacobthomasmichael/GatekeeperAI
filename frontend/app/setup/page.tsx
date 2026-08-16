"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield, CheckCircle, Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// ─── Shared style tokens ────────────────────────────────────────────────────

const inputCls =
  "w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-signal-500";

const primaryBtn =
  "bg-signal-600 hover:bg-signal-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors";

const ghostBtn =
  "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white text-sm transition-colors";

const labelCls = "block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1";

// ─── Helpers ────────────────────────────────────────────────────────────────

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// ─── Step progress dots ─────────────────────────────────────────────────────

function StepDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={
            i < current
              ? "h-2 w-2 rounded-full bg-signal-600"
              : "h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700"
          }
        />
      ))}
    </div>
  );
}

// ─── Wizard data types ──────────────────────────────────────────────────────

interface WizardData {
  company_name: string;
  server_url: string;
  admin_email: string;
  admin_username: string;
  admin_password: string;
  confirm_password: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  smtp_from_email: string;
  smtp_use_tls: boolean;
}

const emptyData: WizardData = {
  company_name: "",
  server_url: "",
  admin_email: "",
  admin_username: "",
  admin_password: "",
  confirm_password: "",
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_password: "",
  smtp_from_email: "",
  smtp_use_tls: true,
};

// ─── Main component ──────────────────────────────────────────────────────────

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState(0); // 0 = checking, 1–5 = wizard steps
  const [data, setData] = useState<WizardData>(emptyData);
  const [errors, setErrors] = useState<Partial<Record<keyof WizardData, string>>>({});
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);

  // On mount: check setup status
  useEffect(() => {
    fetch(`${API}/setup/status`)
      .then((r) => r.json())
      .then((json) => {
        if (json.complete) {
          router.replace("/login");
        } else {
          setStep(1);
        }
      })
      .catch(() => setStep(1)); // if unreachable, show wizard anyway
  }, [router]);

  function set<K extends keyof WizardData>(key: K, value: WizardData[K]) {
    setData((prev) => {
      const next = { ...prev, [key]: value };
      // Auto-populate server_url from company_name
      if (key === "company_name") {
        const slug = toSlug(value as string);
        if (slug) {
          next.server_url = `https://gatekeeper.${slug}.com`;
        } else {
          next.server_url = "";
        }
      }
      return next;
    });
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  function validateStep2(): boolean {
    const e: Partial<Record<keyof WizardData, string>> = {};
    if (data.company_name.trim().length < 2) e.company_name = "Company name must be at least 2 characters.";
    if (!data.server_url.trim().match(/^https?:\/\//)) e.server_url = "Server address must start with http:// or https://";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function validateStep3(): boolean {
    const e: Partial<Record<keyof WizardData, string>> = {};
    if (!data.admin_email.trim()) e.admin_email = "Email is required.";
    if (!data.admin_username.trim().match(/^[a-zA-Z0-9_-]{3,50}$/))
      e.admin_username = "Username must be 3-50 chars: letters, numbers, hyphens, underscores.";
    if (data.admin_password.length < 8) e.admin_password = "Password must be at least 8 characters.";
    if (data.admin_password !== data.confirm_password) e.confirm_password = "Passwords do not match.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleFinish() {
    setSubmitError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/setup/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: data.company_name,
          server_url: data.server_url,
          admin_email: data.admin_email,
          admin_username: data.admin_username,
          admin_password: data.admin_password,
          smtp_host: data.smtp_host,
          smtp_port: data.smtp_port,
          smtp_username: data.smtp_username,
          smtp_password: data.smtp_password,
          smtp_from_email: data.smtp_from_email,
          smtp_use_tls: data.smtp_use_tls,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setSubmitError(body?.detail ?? "Setup failed. Please try again.");
        return;
      }
      setStep(5);
    } catch {
      setSubmitError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── Loading / checking state ─────────────────────────────────────────────
  if (step === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 className="h-6 w-6 animate-spin text-signal-600" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 px-4 py-12">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-800 p-8 w-full max-w-lg">

        {/* ── Step 1: Welcome ─────────────────────────────────────────────── */}
        {step === 1 && (
          <div className="flex flex-col items-center text-center gap-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-signal-50 dark:bg-signal-600/20 border border-signal-200 dark:border-signal-600/30">
              <Shield size={32} className="text-signal-600 dark:text-signal-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Welcome to GatekeeperAI</h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                Let&rsquo;s configure your instance. This only takes a few minutes.
              </p>
            </div>
            <button className={primaryBtn} onClick={() => setStep(2)}>
              Get Started &rarr;
            </button>
          </div>
        )}

        {/* ── Step 2: Company & Server ─────────────────────────────────────── */}
        {step === 2 && (
          <div className="space-y-6">
            <StepDots current={1} total={4} />
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Company &amp; Server</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label className={labelCls}>Company Name</label>
                <input
                  type="text"
                  value={data.company_name}
                  onChange={(e) => set("company_name", e.target.value)}
                  placeholder="Acme Corp"
                  className={inputCls}
                />
                {errors.company_name && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.company_name}</p>
                )}
              </div>
              <div>
                <label className={labelCls}>Server Address</label>
                <input
                  type="text"
                  value={data.server_url}
                  onChange={(e) => set("server_url", e.target.value)}
                  placeholder="https://gatekeeper.acme.com"
                  className={inputCls}
                />
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                  We recommend using a subdomain like https://gatekeeper.yourcompany.com
                </p>
                {errors.server_url && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.server_url}</p>
                )}
              </div>
            </div>
            <div className="flex justify-between pt-2">
              <button className={ghostBtn} onClick={() => setStep(1)}>
                Back
              </button>
              <button
                className={primaryBtn}
                onClick={() => {
                  if (validateStep2()) setStep(3);
                }}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Admin Account ────────────────────────────────────────── */}
        {step === 3 && (
          <div className="space-y-6">
            <StepDots current={2} total={4} />
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Create your admin account</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label className={labelCls}>Email</label>
                <input
                  type="email"
                  value={data.admin_email}
                  onChange={(e) => set("admin_email", e.target.value)}
                  placeholder="admin@company.com"
                  className={inputCls}
                />
                {errors.admin_email && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.admin_email}</p>
                )}
              </div>
              <div>
                <label className={labelCls}>Username</label>
                <input
                  type="text"
                  value={data.admin_username}
                  onChange={(e) => set("admin_username", e.target.value)}
                  placeholder="admin"
                  className={inputCls}
                />
                {errors.admin_username && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.admin_username}</p>
                )}
              </div>
              <div>
                <label className={labelCls}>Password</label>
                <input
                  type="password"
                  value={data.admin_password}
                  onChange={(e) => set("admin_password", e.target.value)}
                  placeholder="••••••••"
                  className={inputCls}
                />
                {errors.admin_password && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.admin_password}</p>
                )}
              </div>
              <div>
                <label className={labelCls}>Confirm Password</label>
                <input
                  type="password"
                  value={data.confirm_password}
                  onChange={(e) => set("confirm_password", e.target.value)}
                  placeholder="••••••••"
                  className={inputCls}
                />
                {errors.confirm_password && (
                  <p className="mt-1 text-xs text-critical-600 dark:text-critical-400">{errors.confirm_password}</p>
                )}
              </div>
            </div>
            <div className="flex justify-between pt-2">
              <button className={ghostBtn} onClick={() => setStep(2)}>
                Back
              </button>
              <button
                className={primaryBtn}
                onClick={() => {
                  if (validateStep3()) setStep(4);
                }}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* ── Step 4: Email Notifications ──────────────────────────────────── */}
        {step === 4 && (
          <div className="space-y-6">
            <StepDots current={3} total={4} />
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Email Notifications</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Optional. Approvers and submitters will be notified by email.
              </p>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className={labelCls}>SMTP Host</label>
                  <input
                    type="text"
                    value={data.smtp_host}
                    onChange={(e) => set("smtp_host", e.target.value)}
                    placeholder="smtp.example.com"
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>Port</label>
                  <input
                    type="number"
                    value={data.smtp_port}
                    onChange={(e) => set("smtp_port", parseInt(e.target.value, 10) || 587)}
                    placeholder="587"
                    className={inputCls}
                  />
                </div>
              </div>
              <div>
                <label className={labelCls}>SMTP Username</label>
                <input
                  type="text"
                  value={data.smtp_username}
                  onChange={(e) => set("smtp_username", e.target.value)}
                  placeholder="smtp@example.com"
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>SMTP Password</label>
                <input
                  type="password"
                  value={data.smtp_password}
                  onChange={(e) => set("smtp_password", e.target.value)}
                  placeholder="••••••••"
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>From Email</label>
                <input
                  type="email"
                  value={data.smtp_from_email}
                  onChange={(e) => set("smtp_from_email", e.target.value)}
                  placeholder="noreply@company.com"
                  className={inputCls}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                <span className="text-sm text-slate-700 dark:text-slate-300">Use TLS</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={data.smtp_use_tls}
                  onClick={() => set("smtp_use_tls", !data.smtp_use_tls)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    data.smtp_use_tls ? "bg-signal-600" : "bg-slate-300 dark:bg-slate-600"
                  }`}
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                      data.smtp_use_tls ? "translate-x-4" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            </div>

            {submitError && (
              <div className="rounded-md bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-700/40 px-3 py-2 text-sm text-critical-600 dark:text-critical-400">
                {submitError}
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <button className={ghostBtn} onClick={() => setStep(3)}>
                Back
              </button>
              <div className="flex items-center gap-3">
                <button
                  className={ghostBtn}
                  disabled={loading}
                  onClick={handleFinish}
                >
                  Skip for now
                </button>
                <button
                  className={`${primaryBtn} flex items-center gap-2`}
                  disabled={loading}
                  onClick={handleFinish}
                >
                  {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                  {loading ? "Setting up…" : "Finish Setup"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 5: Done ─────────────────────────────────────────────────── */}
        {step === 5 && (
          <div className="flex flex-col items-center text-center gap-6">
            <StepDots current={4} total={4} />
            <CheckCircle size={56} className="text-green-500" />
            <div>
              <h2 className="text-2xl font-semibold text-slate-900 dark:text-white">GatekeeperAI is ready</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your instance is configured and good to go.</p>
            </div>
            <div className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-4 text-left space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400">Company</span>
                <span className="font-medium text-slate-900 dark:text-white">{data.company_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400">Server</span>
                <span className="font-medium text-slate-900 dark:text-white break-all">{data.server_url}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400">Admin</span>
                <span className="font-medium text-slate-900 dark:text-white">{data.admin_email}</span>
              </div>
            </div>
            <button className={primaryBtn} onClick={() => router.push("/login")}>
              Go to Dashboard &rarr;
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
