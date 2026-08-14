"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { scansApi, type Scan } from "@/lib/api";
import RiskBadge from "./RiskBadge";
import ScanResultCard from "./ScanResultCard";
import clsx from "clsx";
import { Key, Package, Globe, Eye, Sparkles, Check, Loader2 } from "lucide-react";

interface ScanEvent {
  event: string;
  scanner?: string;
  status?: string;
  severity?: string;
  duration_ms?: number;
  risk_tier?: string;
  risk_score?: number;
  message?: string;
}

interface Props {
  scanId: string;
  initialScan: Scan;
  onComplete?: (scan: Scan) => void;
}

const SCANNER_ORDER = ["secrets", "dependencies", "egress", "pii", "llm"] as const;

const SCANNER_LABELS: Record<string, string> = {
  secrets: "Secrets",
  dependencies: "Dependencies",
  egress: "Egress URLs",
  pii: "PII Detection",
  llm: "AI Analysis",
};

const SCANNER_ICONS: Record<string, React.ReactNode> = {
  secrets: <Key size={15} />,
  dependencies: <Package size={15} />,
  egress: <Globe size={15} />,
  pii: <Eye size={15} />,
  llm: <Sparkles size={15} />,
};

type ScannerState = "waiting" | "running" | "done";

const RING_CIRCUMFERENCE = 2 * Math.PI * 54; // r=54

export default function ScanStream({ scanId, initialScan, onComplete }: Props) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [scan, setScan] = useState<Scan>(initialScan);
  const [done, setDone] = useState(
    initialScan.status === "complete" || initialScan.status === "failed"
  );
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (done) return;
    const token = localStorage.getItem("gka_token");
    const url = scansApi.streamUrl(scanId);
    const es = new EventSource(token ? `${url}?token=${encodeURIComponent(token)}` : url);
    esRef.current = es;

    es.onmessage = async (e) => {
      try {
        const evt: ScanEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, evt]);
        if (evt.event === "complete" || evt.event === "error") {
          es.close();
          setDone(true);
          const updated = await scansApi.get(scanId);
          setScan(updated);
          onComplete?.(updated);
        }
      } catch {}
    };

    es.onerror = () => es.close();
    return () => es.close();
  }, [scanId, done, onComplete]);

  // Derive per-scanner state from the event stream — if the page loads after
  // the scan already finished, scan.scan_results carries the same info.
  const scannerStates = useMemo(() => {
    const states: Record<string, ScannerState> = {};
    for (const name of SCANNER_ORDER) states[name] = "waiting";
    for (const evt of events) {
      if (!evt.scanner) continue;
      if (evt.event === "scanner_started") states[evt.scanner] = "running";
      if (evt.event === "scanner_complete") states[evt.scanner] = "done";
    }
    if (scan.scan_results) {
      for (const r of scan.scan_results) states[r.scanner_name] = "done";
    }
    if (done) {
      for (const name of SCANNER_ORDER) if (states[name] === "waiting") states[name] = "done";
    }
    return states;
  }, [events, scan.scan_results, done]);

  const completedCount = SCANNER_ORDER.filter((n) => scannerStates[n] === "done").length;
  const ringOffset = RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * completedCount) / SCANNER_ORDER.length;
  const errorEvent = events.find((e) => e.event === "error");

  return (
    <div className="space-y-6">
      {/* Progress stage */}
      <div className="grid grid-cols-1 items-center gap-8 rounded-[22px] border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-7 shadow-sm sm:grid-cols-[auto_1fr]">
        <div className="relative mx-auto h-32 w-32 shrink-0">
          <svg viewBox="0 0 120 120" className="h-32 w-32 -rotate-90">
            <circle cx="60" cy="60" r="54" fill="none" strokeWidth="8" className="stroke-slate-100 dark:stroke-slate-800" />
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              strokeWidth="8"
              strokeLinecap="round"
              className={clsx(
                "transition-[stroke-dashoffset] duration-700 ease-out",
                done && !errorEvent ? "stroke-good-500" : "stroke-signal-600"
              )}
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={ringOffset}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              {completedCount}/{SCANNER_ORDER.length}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              {done ? "Complete" : "Scanning"}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-0.5">
          {SCANNER_ORDER.map((name) => {
            const state = scannerStates[name];
            return (
              <div
                key={name}
                className="flex items-center gap-3 border-b border-slate-100 py-2.5 last:border-0 dark:border-slate-800/60"
              >
                <div
                  className={clsx(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors",
                    state === "done" && "bg-good-50 text-good-600 dark:bg-good-950/40 dark:text-good-400",
                    state === "running" && "bg-signal-50 text-signal-600 dark:bg-signal-950/40 dark:text-signal-400",
                    state === "waiting" && "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500"
                  )}
                >
                  {state === "running" ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : state === "done" ? (
                    <Check size={14} />
                  ) : (
                    SCANNER_ICONS[name]
                  )}
                </div>
                <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
                  {SCANNER_LABELS[name]}
                </span>
                <span
                  className={clsx(
                    "text-xs font-medium",
                    state === "done" && "text-good-600 dark:text-good-400",
                    state === "running" && "text-signal-600 dark:text-signal-400",
                    state === "waiting" && "text-slate-400 dark:text-slate-500"
                  )}
                >
                  {state === "done" ? "Clear" : state === "running" ? "Scanning…" : "Waiting"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {errorEvent?.message && (
        <div className="rounded-xl border border-critical-200 bg-critical-50 px-4 py-3 text-sm text-critical-700 dark:border-critical-800/50 dark:bg-critical-950/30 dark:text-critical-300">
          {errorEvent.message}
        </div>
      )}

      {scan.risk_tier && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500 dark:text-slate-400">Result:</span>
          <RiskBadge tier={scan.risk_tier} score={scan.risk_score} />
        </div>
      )}

      {/* Scanner results grid */}
      {scan.scan_results && scan.scan_results.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {scan.scan_results.map((r) => (
            <ScanResultCard key={r.id} result={r} />
          ))}
        </div>
      )}
    </div>
  );
}
