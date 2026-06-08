"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { scansApi, appsApi, type Scan, type AppSubmission } from "@/lib/api";
import ScanStream from "@/components/ScanStream";
import RiskBadge from "@/components/RiskBadge";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<Scan | null>(null);
  const [app, setApp] = useState<AppSubmission | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    scansApi.get(scanId).then(async (s) => {
      setScan(s);
      setLoading(false);
      try {
        const a = await appsApi.get(s.submission_id);
        setApp(a);
      } catch {}
    });
  }, [scanId]);

  if (loading || !scan) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition-colors"
      >
        <ArrowLeft size={14} />
        Back
      </button>

      {/* Header */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-white">
              {app?.name ?? "Scan Report"}
            </h1>
            {app?.description && (
              <p className="mt-1 text-sm text-slate-500">{app.description}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-3">
              <StatusBadge status={scan.status} />
              <RiskBadge tier={scan.risk_tier} score={scan.risk_score} />
            </div>
          </div>
          <div className="text-right text-xs text-slate-600 space-y-1">
            {scan.commit_sha && (
              <p>
                Commit:{" "}
                <code className="text-slate-400">{scan.commit_sha.slice(0, 8)}</code>
              </p>
            )}
            {scan.started_at && (
              <p>Started: {new Date(scan.started_at).toLocaleString()}</p>
            )}
            {scan.completed_at && (
              <p>Completed: {new Date(scan.completed_at).toLocaleString()}</p>
            )}
          </div>
        </div>
      </div>

      {/* Live stream / results */}
      <ScanStream
        scanId={scanId}
        initialScan={scan}
        onComplete={setScan}
      />

      {/* Approval status */}
      {scan.status === "complete" && scan.risk_tier !== "green" && (
        <div className="rounded-lg border border-amber-800/40 bg-amber-900/10 p-4 text-sm text-amber-400">
          This scan requires human review before the app can be deployed.
          An approver has been notified.
        </div>
      )}
      {scan.status === "complete" && scan.risk_tier === "green" && (
        <div className="rounded-lg border border-emerald-800/40 bg-emerald-900/10 p-4 text-sm text-emerald-400">
          Green tier — this app has been automatically approved and queued for deployment.
        </div>
      )}
    </div>
  );
}
