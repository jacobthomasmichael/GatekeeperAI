"use client";

import { useEffect, useState } from "react";
import { deploymentsApi, type Deployment } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { Boxes, ExternalLink, Terminal } from "lucide-react";

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [logs, setLogs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    deploymentsApi.list().then((d) => {
      setDeployments(d);
      setLoading(false);
    });
  }, []);

  async function fetchLogs(d: Deployment) {
    if (!d.container_id) return;
    const { logs: l } = await deploymentsApi.logs(d.id);
    setLogs((prev) => ({ ...prev, [d.id]: l }));
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Deployments</h1>
        <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
          Running containers for approved apps
        </p>
      </div>

      {loading && (
        <div className="flex h-32 items-center justify-center">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-indigo-500" />
        </div>
      )}

      {!loading && deployments.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900/50 p-12 text-center">
          <Boxes size={32} className="mx-auto text-gray-300 dark:text-slate-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-600 dark:text-slate-300">No deployments</h3>
          <p className="text-sm text-gray-400 dark:text-slate-500 mt-1">
            Apps will appear here after they are approved and deployed.
          </p>
        </div>
      )}

      <div className="space-y-4">
        {deployments.map((d) => (
          <div
            key={d.id}
            className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-medium text-gray-900 dark:text-white">
                    {d.container_name ?? d.id.slice(0, 8)}
                  </span>
                  <StatusBadge status={d.status} />
                </div>
                {d.image_tag && (
                  <p className="text-xs text-gray-400 dark:text-slate-600 mt-1">{d.image_tag}</p>
                )}
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-400 dark:text-slate-600">
                  {d.internal_port && (
                    <span>Port: {d.external_port} → {d.internal_port}</span>
                  )}
                  <span>Created: {new Date(d.created_at).toLocaleString()}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {d.public_url && d.status === "running" && (
                  <a
                    href={d.public_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-slate-700 px-3 py-1.5 text-xs text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    <ExternalLink size={12} />
                    Open App
                  </a>
                )}
                {d.container_id && (
                  <button
                    onClick={() => fetchLogs(d)}
                    className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-slate-700 px-3 py-1.5 text-xs text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    <Terminal size={12} />
                    Logs
                  </button>
                )}
              </div>
            </div>

            {logs[d.id] !== undefined && (
              <div className="rounded-lg bg-gray-50 dark:bg-slate-950 border border-gray-200 dark:border-slate-800 p-3 max-h-48 overflow-y-auto">
                <pre className="text-xs text-gray-600 dark:text-slate-400 whitespace-pre-wrap font-mono">
                  {logs[d.id] || "(no output)"}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
