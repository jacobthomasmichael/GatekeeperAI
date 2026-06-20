"use client";

import { useEffect, useRef, useState } from "react";
import { scansApi, type Scan } from "@/lib/api";
import RiskBadge from "./RiskBadge";
import ScanResultCard from "./ScanResultCard";
import clsx from "clsx";

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

const SCANNER_LABELS: Record<string, string> = {
  secrets: "Secrets",
  dependencies: "Dependencies",
  egress: "Egress URLs",
  pii: "PII Detection",
  llm: "AI Analysis",
};

export default function ScanStream({ scanId, initialScan, onComplete }: Props) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [scan, setScan] = useState<Scan>(initialScan);
  const [done, setDone] = useState(
    initialScan.status === "complete" || initialScan.status === "failed"
  );
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="space-y-6">
      {/* Status header */}
      <div className="flex items-center gap-4">
        {!done && <div className="h-3 w-3 animate-pulse rounded-full bg-blue-400" />}
        <span className="text-sm text-gray-500 dark:text-slate-400">
          {done ? "Scan complete" : "Scan in progress..."}
        </span>
        {scan.risk_tier && <RiskBadge tier={scan.risk_tier} score={scan.risk_score} />}
      </div>

      {/* Live event log */}
      {events.length > 0 && (
        <div className="rounded-lg border border-gray-200 dark:border-slate-800 bg-gray-50 dark:bg-slate-950 p-4 font-mono text-xs space-y-1.5 max-h-64 overflow-y-auto">
          {events.map((evt, i) => (
            <div key={i} className="flex gap-3">
              <span className="text-gray-300 dark:text-slate-600 select-none">{i + 1}</span>
              <span
                className={clsx(
                  evt.event === "error"            && "text-red-600 dark:text-red-400",
                  evt.event === "complete"         && "text-emerald-600 dark:text-emerald-400",
                  evt.event === "scanner_complete" && "text-blue-600 dark:text-blue-400",
                  evt.event === "started"          && "text-gray-500 dark:text-slate-400",
                  evt.event === "scanner_started"  && "text-gray-400 dark:text-slate-500"
                )}
              >
                [{evt.event}]
              </span>
              {evt.scanner && (
                <span className="text-gray-700 dark:text-slate-300">
                  {SCANNER_LABELS[evt.scanner] ?? evt.scanner}
                </span>
              )}
              {evt.severity && evt.severity !== "none" && (
                <span className="text-gray-400 dark:text-slate-400">
                  {evt.severity}
                </span>
              )}
              {evt.duration_ms && (
                <span className="text-gray-300 dark:text-slate-600">{evt.duration_ms}ms</span>
              )}
              {evt.message && <span className="text-red-600 dark:text-red-400">{evt.message}</span>}
              {evt.risk_tier && (
                <span className="text-gray-700 dark:text-slate-300">
                  → {evt.risk_tier} (score: {evt.risk_score})
                </span>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
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
