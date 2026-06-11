"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { deploymentsApi, authApi, type Deployment } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import {
  Boxes,
  ExternalLink,
  Terminal,
  RefreshCw,
  Square,
  Play,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";

// ── Timeline ──────────────────────────────────────────────────────────────────

function TimelineRow({
  icon,
  label,
  ts,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  ts: string | null;
  active?: boolean;
}) {
  return (
    <div className={`flex items-start gap-3 ${!ts ? "opacity-30" : ""}`}>
      <div
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
          active
            ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400"
            : ts
            ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
            : "bg-gray-100 dark:bg-slate-800 text-gray-400 dark:text-slate-600"
        }`}
      >
        {icon}
      </div>
      <div>
        <p className="text-xs font-medium text-gray-700 dark:text-slate-300">{label}</p>
        {ts && (
          <p className="text-xs text-gray-400 dark:text-slate-500">
            {new Date(ts).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Log pane ──────────────────────────────────────────────────────────────────

function LogPane({ deploymentId, hasContainer }: { deploymentId: string; hasContainer: boolean }) {
  const [logs, setLogs] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLPreElement>(null);

  const fetchLogs = useCallback(async () => {
    if (!hasContainer) return;
    setLoading(true);
    try {
      const { logs: l } = await deploymentsApi.logs(deploymentId);
      setLogs(l || "(no output)");
    } finally {
      setLoading(false);
    }
  }, [deploymentId, hasContainer]);

  useEffect(() => {
    if (open) fetchLogs();
  }, [open, fetchLogs]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  if (!hasContainer) return null;

  return (
    <div className="border-t border-gray-100 dark:border-slate-800 pt-4">
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-400 dark:text-slate-500 hover:text-gray-700 dark:hover:text-slate-200 transition-colors"
        >
          <Terminal size={13} />
          Container Logs
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
        {open && (
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-slate-500 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="h-3 w-3 rounded border-gray-300"
              />
              Auto-scroll
            </label>
            <button
              onClick={fetchLogs}
              disabled={loading}
              className="flex items-center gap-1 text-xs text-gray-400 dark:text-slate-500 hover:text-gray-700 dark:hover:text-slate-200"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        )}
      </div>

      {open && (
        <div className="rounded-lg bg-gray-950 dark:bg-black border border-gray-800 p-3 max-h-64 overflow-y-auto">
          {loading && logs === null ? (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Loader2 size={13} className="animate-spin" />
              Loading…
            </div>
          ) : (
            <pre
              ref={scrollRef}
              className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed max-h-56 overflow-y-auto"
            >
              {logs ?? ""}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Deployment card ───────────────────────────────────────────────────────────

function DeploymentCard({
  deployment: initial,
  isAdmin,
}: {
  deployment: Deployment;
  isAdmin: boolean;
}) {
  const [d, setD] = useState(initial);
  const [actioning, setActioning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const { status, public_url } = await deploymentsApi.status(d.id);
        setD((prev) => ({ ...prev, status, public_url: public_url ?? prev.public_url }));
        if (status !== "starting") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
        }
      } catch {}
    }, 3000);
  }, [d.id]);

  useEffect(() => {
    if (d.status === "starting") startPolling();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [d.status, startPolling]);

  const handleStop = async () => {
    setActioning(true);
    try {
      const updated = await deploymentsApi.stop(d.id);
      setD(updated);
    } finally {
      setActioning(false);
    }
  };

  const handleStart = async () => {
    setActioning(true);
    try {
      const updated = await deploymentsApi.start(d.id);
      setD(updated);
      startPolling();
    } finally {
      setActioning(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold text-gray-900 dark:text-white">
              {d.container_name ?? d.id.slice(0, 8)}
            </span>
            <StatusBadge status={d.status} />
            {d.status === "starting" && (
              <Loader2 size={14} className="animate-spin text-indigo-500" />
            )}
          </div>
          {d.image_tag && (
            <p className="text-xs text-gray-400 dark:text-slate-600 mt-1 font-mono">{d.image_tag}</p>
          )}
          {d.internal_port && (
            <p className="text-xs text-gray-400 dark:text-slate-600 mt-0.5">
              Port mapping: :{d.external_port} → :{d.internal_port}
            </p>
          )}
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
          {isAdmin && d.status === "running" && (
            <button
              onClick={handleStop}
              disabled={actioning}
              className="flex items-center gap-1.5 rounded-md border border-red-200 dark:border-red-800/60 px-3 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 disabled:opacity-50 transition-colors"
            >
              <Square size={11} />
              Stop
            </button>
          )}
          {isAdmin && (d.status === "stopped" || d.status === "failed") && (
            <button
              onClick={handleStart}
              disabled={actioning}
              className="flex items-center gap-1.5 rounded-md border border-emerald-200 dark:border-emerald-800/60 px-3 py-1.5 text-xs text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 disabled:opacity-50 transition-colors"
            >
              <Play size={11} />
              Restart
            </button>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-wider">
          Timeline
        </p>
        <div className="space-y-2.5">
          <TimelineRow
            icon={<Clock size={12} />}
            label="Created"
            ts={d.created_at}
          />
          <TimelineRow
            icon={
              d.status === "starting" ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <CheckCircle2 size={12} />
              )
            }
            label="Started"
            ts={d.started_at}
            active={d.status === "starting"}
          />
          <TimelineRow
            icon={<XCircle size={12} />}
            label="Stopped"
            ts={d.stopped_at}
          />
        </div>
      </div>

      {/* Logs */}
      <LogPane deploymentId={d.id} hasContainer={!!d.container_id} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([deploymentsApi.list(), authApi.me()]).then(([list, me]) => {
      setDeployments(list);
      setIsAdmin(me.role === "admin");
      setLoading(false);
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
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Deployments</h1>
          <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
            {deployments.length} deployment{deployments.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          onClick={() => {
            setLoading(true);
            deploymentsApi.list().then((d) => { setDeployments(d); setLoading(false); });
          }}
          className="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-slate-700 px-3 py-1.5 text-xs text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {deployments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900/50 p-12 text-center">
          <Boxes size={32} className="mx-auto text-gray-300 dark:text-slate-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-600 dark:text-slate-300">No deployments</h3>
          <p className="text-sm text-gray-400 dark:text-slate-500 mt-1">
            Apps appear here after they are approved and deployed.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {deployments.map((d) => (
            <DeploymentCard key={d.id} deployment={d} isAdmin={isAdmin} />
          ))}
        </div>
      )}
    </div>
  );
}
