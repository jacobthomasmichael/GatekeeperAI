"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { deploymentsApi, appsApi, authApi, type Deployment } from "@/lib/api";
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
  Lock,
  Globe,
  Flag,
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
            ? "bg-signal-100 dark:bg-signal-900/40 text-signal-600 dark:text-signal-400"
            : ts
            ? "bg-good-50 dark:bg-good-900/30 text-good-600 dark:text-good-400"
            : "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600"
        }`}
      >
        {icon}
      </div>
      <div>
        <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{label}</p>
        {ts && (
          <p className="text-xs text-slate-400 dark:text-slate-500">
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
    <div className="border-t border-slate-100 dark:border-slate-800 pt-4">
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          <Terminal size={13} />
          Container Logs
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
        {open && (
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="h-3 w-3 rounded border-slate-300"
              />
              Auto-scroll
            </label>
            <button
              onClick={fetchLogs}
              disabled={loading}
              className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        )}
      </div>

      {open && (
        <div className="rounded-lg bg-slate-950 dark:bg-black border border-slate-800 p-3 max-h-64 overflow-y-auto">
          {loading && logs === null ? (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 size={13} className="animate-spin" />
              Loading…
            </div>
          ) : (
            <pre
              ref={scrollRef}
              className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed max-h-56 overflow-y-auto"
            >
              {logs ?? ""}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Visibility toggle ─────────────────────────────────────────────────────────

function VisibilityToggle({
  submissionId,
  visibility,
  onChange,
}: {
  submissionId: string;
  visibility: string | null;
  onChange: (v: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const isPublic = visibility === "public";

  const toggle = async () => {
    if (!isPublic) {
      setConfirming(true);
      return;
    }
    setBusy(true);
    try {
      await appsApi.updateVisibility(submissionId, "private");
      onChange("private");
    } finally {
      setBusy(false);
    }
  };

  const confirmPublic = async () => {
    setBusy(true);
    setConfirming(false);
    try {
      await appsApi.updateVisibility(submissionId, "public");
      onChange("public");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {confirming && (
        <div className="flex items-center gap-2 rounded-lg border border-warn-200 dark:border-warn-700 bg-warn-50 dark:bg-warn-900/20 px-3 py-2 text-xs text-warn-800 dark:text-warn-300">
          <Flag size={12} className="shrink-0" />
          <span>Making this app public will flag it for admin review.</span>
          <button
            onClick={confirmPublic}
            className="ml-1 font-semibold underline hover:no-underline"
          >
            Confirm
          </button>
          <button onClick={() => setConfirming(false)} className="hover:underline">
            Cancel
          </button>
        </div>
      )}
      <button
        onClick={toggle}
        disabled={busy || confirming}
        title={isPublic ? "Click to require login" : "Click to make public"}
        className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
          isPublic
            ? "border-warn-300 dark:border-warn-700 bg-warn-50 dark:bg-warn-900/20 text-warn-800 dark:text-warn-400 hover:bg-warn-100 dark:hover:bg-warn-900/40"
            : "border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
        }`}
      >
        {busy ? (
          <Loader2 size={11} className="animate-spin" />
        ) : isPublic ? (
          <Globe size={11} />
        ) : (
          <Lock size={11} />
        )}
        {isPublic ? "Public" : "Private"}
      </button>
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
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold text-slate-900 dark:text-white">
              {d.container_name ?? d.id.slice(0, 8)}
            </span>
            <StatusBadge status={d.status} />
            {d.status === "starting" && (
              <Loader2 size={14} className="animate-spin text-signal-500" />
            )}
          </div>
          {d.image_tag && (
            <p className="text-xs text-slate-400 dark:text-slate-600 mt-1 font-mono">{d.image_tag}</p>
          )}
          {d.internal_port && (
            <p className="text-xs text-slate-400 dark:text-slate-600 mt-0.5">
              Port mapping: :{d.external_port} → :{d.internal_port}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {d.status === "running" && (
            <VisibilityToggle
              submissionId={d.submission_id}
              visibility={d.app_visibility}
              onChange={(v) => setD((prev) => ({ ...prev, app_visibility: v }))}
            />
          )}
          {d.public_url && d.status === "running" && (
            <a
              href={d.public_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              <ExternalLink size={12} />
              Open App
            </a>
          )}
          {isAdmin && d.status === "running" && (
            <button
              onClick={handleStop}
              disabled={actioning}
              className="flex items-center gap-1.5 rounded-md border border-critical-200 dark:border-critical-800/60 px-3 py-1.5 text-xs text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/30 disabled:opacity-50 transition-colors"
            >
              <Square size={11} />
              Stop
            </button>
          )}
          {isAdmin && (d.status === "stopped" || d.status === "failed") && (
            <button
              onClick={handleStart}
              disabled={actioning}
              className="flex items-center gap-1.5 rounded-md border border-good-200 dark:border-good-800/60 px-3 py-1.5 text-xs text-good-700 dark:text-good-400 hover:bg-good-50 dark:hover:bg-good-900/30 disabled:opacity-50 transition-colors"
            >
              <Play size={11} />
              Restart
            </button>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
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
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Deployments</h1>
          <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
            {deployments.length} deployment{deployments.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          onClick={() => {
            setLoading(true);
            deploymentsApi.list().then((d) => { setDeployments(d); setLoading(false); });
          }}
          className="flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {deployments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900/50 p-12 text-center">
          <Boxes size={32} className="mx-auto text-slate-300 dark:text-slate-600 mb-3" />
          <h3 className="text-sm font-medium text-slate-600 dark:text-slate-300">No deployments</h3>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
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
