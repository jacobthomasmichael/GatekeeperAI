"use client";

import { Suspense, useState, FormEvent, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError, passkeyApi, ssoApi, SSOPublicConfig } from "@/lib/api";
import { Shield, Fingerprint, KeyRound, Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL!;

function LoginForm() {
  const { user, login, loginWithTokens } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [usePassword, setUsePassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ssoConfig, setSsoConfig] = useState<SSOPublicConfig | null>(null);
  const [ssoLoading, setSsoLoading] = useState(false);

  const next = searchParams.get("next") || "/dashboard";
  const ssoCode = searchParams.get("sso_code");
  const ssoError = searchParams.get("error");

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, router, next]);

  useEffect(() => {
    ssoApi.getPublicConfig().then(setSsoConfig).catch(() => null);
  }, []);

  useEffect(() => {
    if (!ssoCode) return;
    setSsoLoading(true);
    ssoApi.exchange(ssoCode)
      .then(async (tokens) => {
        await loginWithTokens(tokens.access_token, tokens.refresh_token);
        router.replace(next);
      })
      .catch(() => {
        setError("SSO sign-in expired or failed. Please try again.");
        setSsoLoading(false);
      });
  }, [ssoCode]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (ssoError) {
      setError(
        ssoError === "sso_not_configured"
          ? "SSO is not configured."
          : "SSO sign-in failed. Please try again or use a local account."
      );
    }
  }, [ssoError]);

  async function handlePasskey(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { startAuthentication } = await import("@simplewebauthn/browser");
      const options = await passkeyApi.authenticateBegin(email);
      const credential = await startAuthentication({ optionsJSON: options as never });
      const tokens = await passkeyApi.authenticateComplete(credential);
      await loginWithTokens(tokens.access_token, tokens.refresh_token);
      router.push(next);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error && err.name === "NotAllowedError") {
        setError("Passkey prompt was dismissed.");
      } else {
        setError("Passkey sign-in failed. Try again or use your password.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handlePassword(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-signal-500 focus:outline-none focus:ring-1 focus:ring-signal-500";

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-signal-50 dark:bg-signal-600/20 border border-signal-200 dark:border-signal-600/30">
            <Shield size={24} className="text-signal-600 dark:text-signal-400" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">GatekeeperAI</h1>
            <p className="text-sm text-slate-400 dark:text-slate-500">Secure enterprise app runtime</p>
          </div>
        </div>

        {ssoLoading && (
          <div className="flex items-center justify-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-4">
            <Loader2 size={16} className="animate-spin" />
            Completing SSO sign-in…
          </div>
        )}

        <div className="rounded-[22px] border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-7 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Sign in</h2>

          {ssoConfig?.enabled && !ssoLoading && (
            <>
              <a
                href={`${API_BASE}/auth/sso/authorize?next=${encodeURIComponent(next)}`}
                className="w-full flex items-center justify-center gap-2 rounded-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2.5 text-sm font-bold text-slate-800 dark:text-white transition-colors hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                <Shield size={16} className="text-signal-500" />
                Sign in with {ssoConfig.provider_name || "SSO"}
              </a>
              <div className="flex items-center gap-3">
                <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
                <span className="text-xs text-slate-400 dark:text-slate-500">or</span>
                <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
              </div>
            </>
          )}

          {error && (
            <div className="rounded-md bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-700/40 px-3 py-2 text-sm text-critical-600 dark:text-critical-400">
              {error}
            </div>
          )}

          {/* Email — shared by both flows */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username webauthn"
              placeholder="you@company.com"
              className={inputCls}
            />
          </div>

          {!usePassword ? (
            /* ── Passkey flow (default) ── */
            <form onSubmit={handlePasskey} className="space-y-4">
              <button
                type="submit"
                disabled={loading || !email}
                className="w-full flex items-center justify-center gap-2 rounded-full bg-signal-600 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:bg-signal-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Fingerprint size={16} />
                )}
                {loading ? "Waiting for passkey…" : "Sign in with passkey"}
              </button>
              <p className="text-center text-xs text-slate-400 dark:text-slate-500">
                No passkey yet?{" "}
                <button
                  type="button"
                  onClick={() => { setUsePassword(true); setError(""); }}
                  className="text-signal-500 hover:text-signal-400 underline underline-offset-2"
                >
                  Use password instead
                </button>
              </p>
            </form>
          ) : (
            /* ── Password flow (fallback) ── */
            <form onSubmit={handlePassword} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className={inputCls}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 rounded-full bg-signal-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-signal-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />}
                {loading ? "Signing in…" : "Sign in with password"}
              </button>
              <p className="text-center text-xs text-slate-400 dark:text-slate-500">
                <button
                  type="button"
                  onClick={() => { setUsePassword(false); setError(""); }}
                  className="text-signal-500 hover:text-signal-400 underline underline-offset-2"
                >
                  Use passkey instead
                </button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
