"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { appsApi, scansApi, type AppSubmission, type Scan } from "@/lib/api";
import SecretsManager from "@/components/SecretsManager";
import RiskBadge from "@/components/RiskBadge";
import StatusBadge from "@/components/StatusBadge";
import { PlusCircle, GitBranch, ExternalLink } from "lucide-react";

export default function DashboardPage() {
  const [apps, setApps] = useState<AppSubmission[]>([]);
  const [latestScans, setLatestScans] = useState<Record<string, Scan>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    appsApi.list().then(async (list) => {
      setApps(list);
      setLoading(false);
      const scansMap: Record<string, Scan> = {};
      await Promise.all(
        list.map(async (app) => {
          try {
            const scans = await scansApi.listForApp(app.id);
            if (scans.length > 0) scansMap[app.id] = scans[0];
          } catch {}
        })
      );
      setLatestScans(scansMap);
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
                  {scan && (
                    <Link
                      href={`/dashboard/scans/${scan.id}`}
                      className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-slate-700 px-3 py-1.5 text-xs text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      <ExternalLink size={12} />
                      Scan Report
                    </Link>
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

              {/* Clone URL */}
              <CloneUrl appId={app.id} repoUrl={app.repo_url} />

              {/* Secrets */}
              <SecretsManager appId={app.id} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CloneUrl({ appId, repoUrl }: { appId: string; repoUrl: string }) {
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [copied, setCopied] = useState(false);
  const [sshUrl, setSshUrl] = useState<string | null>(null);

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

  return (
    <div className="mt-3 space-y-2">
      <div className="flex gap-1">
        <button
          onClick={() => setMode("new")}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            mode === "new"
              ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300"
              : "text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300"
          }`}
        >
          New project
        </button>
        <button
          onClick={() => setMode("existing")}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            mode === "existing"
              ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300"
              : "text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300"
          }`}
        >
          Existing repo
        </button>
      </div>

      {mode === "new" ? (
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
      ) : (
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
