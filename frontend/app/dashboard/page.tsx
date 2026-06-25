"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { appsApi, authApi, deploymentsApi, scansApi, type AppSubmission, type Deployment, type Scan, type User } from "@/lib/api";
import AppAccessManager from "@/components/AppAccessManager";
import AppGroupsManager from "@/components/AppGroupsManager";
import SecretsManager from "@/components/SecretsManager";
import { ssoApi, type SSOPublicConfig } from "@/lib/api";
import RiskBadge from "@/components/RiskBadge";
import StatusBadge from "@/components/StatusBadge";
import { PlusCircle, GitBranch, ExternalLink, RefreshCw } from "lucide-react";

type ContainerHealth = { status: string; restart_count: number; logs: string | null };

export default function DashboardPage() {
  const [apps, setApps] = useState<AppSubmission[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [latestScans, setLatestScans] = useState<Record<string, Scan>>({});
  const [deployments, setDeployments] = useState<Record<string, Deployment>>({});
  const [containerHealth, setContainerHealth] = useState<Record<string, ContainerHealth>>({});
  const [loading, setLoading] = useState(true);
  const [ssoConfig, setSsoConfig] = useState<SSOPublicConfig | null>(null);

  useEffect(() => {
    ssoApi.getPublicConfig().then(setSsoConfig).catch(() => null);
  }, []);

  useEffect(() => {
    Promise.all([appsApi.list(), authApi.me()]).then(async ([list, me]) => {
      setApps(list);
      setCurrentUser(me);
      setLoading(false);
      const scansMap: Record<string, Scan> = {};
      const deploymentsMap: Record<string, Deployment> = {};
      const healthMap: Record<string, ContainerHealth> = {};
      await Promise.all(
        list.map(async (app) => {
          try {
            const scans = await scansApi.listForApp(app.id);
            if (scans.length > 0) scansMap[app.id] = scans[0];
          } catch {}
          if (app.status === "deployed") {
            try {
              deploymentsMap[app.id] = await deploymentsApi.getForApp(app.id);
            } catch {}
            try {
              healthMap[app.id] = await deploymentsApi.health(app.id);
            } catch {}
          }
        })
      );
      setLatestScans(scansMap);
      setDeployments(deploymentsMap);
      setContainerHealth(healthMap);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">My Apps</h1>
          <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
            {apps.length} app{apps.length !== 1 ? "s" : ""} registered
          </p>
        </div>
        <Link
          href="/dashboard/submit"
          className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          <PlusCircle size={16} />
          Submit App
        </Link>
      </div>

      {/* Empty state */}
      {apps.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900/50 p-12 text-center">
          <GitBranch size={32} className="mx-auto text-gray-300 dark:text-slate-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-600 dark:text-slate-300">No apps yet</h3>
          <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
            Submit your first app to get started.
          </p>
          <Link
            href="/dashboard/submit"
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            <PlusCircle size={14} />
            Submit App
          </Link>
        </div>
      )}

      {/* App list */}
      <div className="space-y-3">
        {apps.map((app) => {
          const scan = latestScans[app.id];
          const deployment = deployments[app.id];
          const health = containerHealth[app.id];
          const isCrashing = health && ["restarting", "exited", "dead"].includes(health.status);
          return (
            <div
              key={app.id}
              className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 hover:border-gray-300 dark:hover:border-slate-700 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="font-medium text-gray-900 dark:text-white truncate">{app.name}</h3>
                    <StatusBadge status={app.status} />
                    {app.risk_tier && <RiskBadge tier={app.risk_tier} size="sm" />}
                  </div>
                  {app.description && (
                    <p className="mt-1 text-sm text-gray-400 dark:text-slate-500 line-clamp-1">
                      {app.description}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-400 dark:text-slate-600">
                    {app.detected_type && <span>Type: {app.detected_type}</span>}
                    <span>Created: {new Date(app.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {deployment?.public_url && (
                    <a
                      href={deployment.public_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 rounded-md border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1.5 text-xs font-medium text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors"
                    >
                      <ExternalLink size={12} />
                      Open App
                    </a>
                  )}
                  {scan && (
                    <Link
                      href={`/dashboard/scans/${scan.id}`}
                      className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-slate-700 px-3 py-1.5 text-xs text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      <ExternalLink size={12} />
                      Scan Report
                    </Link>
                  )}
                  {app.status === "deployed" && (
                    <UpdateAppButton appId={app.id} />
                  )}
                </div>
              </div>

              {/* Rejection feedback banner */}
              {app.rejection && (
                <div className="mt-4 rounded-lg border border-red-200 dark:border-red-800/60 bg-red-50 dark:bg-red-950/40 p-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 h-2 w-2 rounded-full bg-red-500 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-red-600 dark:text-red-400">
                        Rejected by reviewer
                        <span className="ml-2 text-xs font-normal text-red-400 dark:text-red-600">
                          {new Date(app.rejection.decided_at).toLocaleDateString()}
                        </span>
                      </p>
                      <p className="mt-1 text-sm text-red-600/80 dark:text-red-300/80 leading-snug">
                        {app.rejection.comment}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Container crash banner */}
              {isCrashing && (
                <ContainerErrorPanel health={health} appId={app.id} />
              )}

              {/* Clone URL */}
              <CloneUrl appId={app.id} repoUrl={app.repo_url} />

              {/* Secrets */}
              <SecretsManager appId={app.id} />

              {/* Access control */}
              <AppAccessManager
                appId={app.id}
                isOwner={currentUser?.id === app.submitter_id}
              />
              <AppGroupsManager
                appId={app.id}
                isOwner={currentUser?.id === app.submitter_id}
                ssoEnabled={ssoConfig?.enabled ?? false}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CloneUrl({ appId, repoUrl }: { appId: string; repoUrl: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<"upload" | "new" | "existing">("upload");
  const [copied, setCopied] = useState(false);
  const [sshUrl, setSshUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    import("@/lib/api").then(({ appsApi }) =>
      appsApi.cloneUrl(appId).then((r) => setSshUrl(r.ssh_clone_url)).catch(() => {})
    );
  }, [appId]);

  const remoteUrl = sshUrl ?? repoUrl;
  const newProjectCmd = `git clone ${remoteUrl}`;
  const existingCmd = `git remote add gatekeeper ${remoteUrl}`;
  const pushCmd = `git push gatekeeper main`;

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      const { appsApi } = await import("@/lib/api");
      const { scan_id } = await appsApi.uploadZip(appId, file);
      router.push(`/dashboard/scans/${scan_id}`);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  const tabClass = (t: typeof mode) =>
    `rounded px-2.5 py-1 text-xs font-medium transition-colors ${
      mode === t
        ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300"
        : "text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300"
    }`;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex gap-1">
        <button onClick={() => setMode("upload")} className={tabClass("upload")}>Upload ZIP</button>
        <button onClick={() => setMode("new")} className={tabClass("new")}>New project</button>
        <button onClick={() => setMode("existing")} className={tabClass("existing")}>Existing repo</button>
      </div>

      {mode === "upload" && (
        <div className="space-y-2">
          <p className="text-xs text-gray-400 dark:text-slate-500">
            Compress your app folder into a <code>.zip</code> file and upload it here — no git required.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={handleUpload}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-md border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-950/40 px-3 py-2 text-xs font-medium text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
                Uploading & scanning…
              </>
            ) : (
              "Choose ZIP file"
            )}
          </button>
          {uploadError && (
            <p className="text-xs text-red-500">{uploadError}</p>
          )}
        </div>
      )}

      {mode === "new" && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-400 dark:text-slate-500">
            Clone and start pushing — scans trigger automatically on each push to main.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded bg-gray-50 dark:bg-slate-950 px-3 py-1.5 text-xs text-gray-500 dark:text-slate-400 border border-gray-200 dark:border-slate-800">
              {newProjectCmd}
            </code>
            <button
              onClick={() => copy(newProjectCmd)}
              className="rounded border border-gray-200 dark:border-slate-700 px-2.5 py-1.5 text-xs text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors shrink-0"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
      )}

      {mode === "existing" && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-400 dark:text-slate-500">
            Add GatekeeperAI as a remote — each push to main triggers a scan automatically.
          </p>
          {[existingCmd, pushCmd].map((cmd) => (
            <div key={cmd} className="flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-gray-50 dark:bg-slate-950 px-3 py-1.5 text-xs text-gray-500 dark:text-slate-400 border border-gray-200 dark:border-slate-800">
                {cmd}
              </code>
              <button
                onClick={() => copy(cmd)}
                className="rounded border border-gray-200 dark:border-slate-700 px-2.5 py-1.5 text-xs text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors shrink-0"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ContainerErrorPanel({ health, appId }: { health: ContainerHealth; appId: string }) {
  const [showLogs, setShowLogs] = useState(false);

  const statusLabel = health.status === "restarting"
    ? "crash-looping (restarting repeatedly)"
    : health.status === "exited"
    ? "exited unexpectedly"
    : health.status;

  return (
    <div className="mt-4 rounded-lg border border-amber-200 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/30 p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 h-2 w-2 rounded-full bg-amber-500 shrink-0 animate-pulse" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
            Container is {statusLabel}
            {health.restart_count > 0 && (
              <span className="ml-2 text-xs font-normal text-amber-500 dark:text-amber-600">
                {health.restart_count} restart{health.restart_count !== 1 ? "s" : ""}
              </span>
            )}
          </p>
          <p className="mt-1 text-xs text-amber-600/80 dark:text-amber-300/70 leading-relaxed">
            Your app is deployed but failing to start. Common causes:
          </p>
          <ul className="mt-1.5 text-xs text-amber-600/80 dark:text-amber-300/70 space-y-0.5 list-disc list-inside">
            <li>A dependency version mismatch — check that APIs you use exist in your pinned version</li>
            <li>A missing import or syntax error in <code className="font-mono">app.py</code></li>
            <li>An environment variable your app expects that hasn&apos;t been added to Secrets</li>
            <li>Using <code className="font-mono">st.context</code> requires <code className="font-mono">streamlit&gt;=1.37</code> — pin to <code className="font-mono">streamlit==1.40.0</code></li>
          </ul>
          {health.logs && (
            <div className="mt-3">
              <button
                onClick={() => setShowLogs(v => !v)}
                className="text-xs text-amber-600 dark:text-amber-400 hover:underline font-medium"
              >
                {showLogs ? "Hide logs ↑" : "View error logs ↓"}
              </button>
              {showLogs && (
                <pre className="mt-2 rounded bg-slate-950 p-3 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap leading-5 max-h-48 overflow-y-auto">
                  {health.logs.trim()}
                </pre>
              )}
            </div>
          )}
          <p className="mt-3 text-xs text-amber-600/70 dark:text-amber-400/60">
            Fix the issue and use <strong>Update App</strong> to upload a corrected zip.
          </p>
        </div>
      </div>
    </div>
  );
}

function UpdateAppButton({ appId }: { appId: string }) {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const { scan_id } = await appsApi.uploadZip(appId, file);
      router.push(`/dashboard/scans/${scan_id}`);
    } catch {
      setError("Upload failed — please try again.");
      setUploading(false);
    }
  }

  return (
    <div>
      <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={handleFile} />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        className="flex items-center gap-1.5 rounded-md border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 px-3 py-1.5 text-xs text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors disabled:opacity-50"
      >
        <RefreshCw size={12} className={uploading ? "animate-spin" : ""} />
        {uploading ? "Uploading…" : "Update App"}
      </button>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
