"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { appsApi, scansApi, type AppSubmission, type Scan } from "@/lib/api";
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
      // fetch latest scan for each app
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
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">My Apps</h1>
          <p className="mt-1 text-sm text-slate-500">
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
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 p-12 text-center">
          <GitBranch size={32} className="mx-auto text-slate-600 mb-3" />
          <h3 className="text-sm font-medium text-slate-300">No apps yet</h3>
          <p className="mt-1 text-sm text-slate-500">
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
              className="rounded-xl border border-slate-800 bg-slate-900 p-5 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="font-medium text-white truncate">{app.name}</h3>
                    <StatusBadge status={app.status} />
                    {app.risk_tier && (
                      <RiskBadge tier={app.risk_tier} size="sm" />
                    )}
                  </div>
                  {app.description && (
                    <p className="mt-1 text-sm text-slate-500 line-clamp-1">
                      {app.description}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
                    {app.detected_type && (
                      <span>Type: {app.detected_type}</span>
                    )}
                    <span>
                      Created:{" "}
                      {new Date(app.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {scan && (
                    <Link
                      href={`/dashboard/scans/${scan.id}`}
                      className="flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
                    >
                      <ExternalLink size={12} />
                      Scan Report
                    </Link>
                  )}
                </div>
              </div>

              {/* Clone URL */}
              <CloneUrl appId={app.id} repoUrl={app.repo_url} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CloneUrl({ appId, repoUrl }: { appId: string; repoUrl: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(repoUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="mt-3 flex items-center gap-2">
      <code className="flex-1 truncate rounded bg-slate-950 px-3 py-1.5 text-xs text-slate-400 border border-slate-800">
        git clone {repoUrl}
      </code>
      <button
        onClick={copy}
        className="rounded border border-slate-700 px-2.5 py-1.5 text-xs text-slate-400 hover:bg-slate-800 transition-colors shrink-0"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
