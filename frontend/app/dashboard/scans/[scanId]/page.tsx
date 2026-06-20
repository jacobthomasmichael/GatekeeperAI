"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  scansApi,
  appsApi,
  deploymentsApi,
  type Scan,
  type AppSubmission,
  type Deployment,
} from "@/lib/api";
import ScanStream from "@/components/ScanStream";
import RiskBadge from "@/components/RiskBadge";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft, ExternalLink, CheckCircle, Loader2 } from "lucide-react";

type DeployPhase = "idle" | "deploying" | "live" | "failed";

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<Scan | null>(null);
  const [app, setApp] = useState<AppSubmission | null>(null);
  const [loading, setLoading] = useState(true);
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [deployPhase, setDeployPhase] = useState<DeployPhase>("idle");

  useEffect(() => {
    scansApi.get(scanId).then(async (s) => {
      setScan(s);
      setLoading(false);
      try {
        const a = await appsApi.get(s.submission_id);
        setApp(a);
      } catch {}
      // Page loaded after scan already completed (e.g. refresh)
      if (s.status === "complete" && s.risk_tier === "green") {
        setDeployPhase("deploying");
      }
    });
  }, [scanId]);

  // Poll for deployment once scan is green-approved
  useEffect(() => {
    if (deployPhase !== "deploying" || !scan) return;
    let cancelled = false;

    async function poll() {
      if (cancelled || !scan) return;
      try {
        const d = await deploymentsApi.getForApp(scan.submission_id);
        if (cancelled) return;
        setDeployment(d);
        if (d.status === "running" && d.public_url) {
          setDeployPhase("live");
        } else if (d.status === "failed" || d.status === "error") {
          setDeployPhase("failed");
        } else {
          setTimeout(poll, 2000);
        }
      } catch {
        // Deployment record not created yet — keep waiting
        if (!cancelled) setTimeout(poll, 2000);
      }
    }

    poll();
    return () => { cancelled = true; };
  }, [deployPhase, scan]);

  const handleScanComplete = useCallback((updatedScan: Scan) => {
    setScan(updatedScan);
    if (updatedScan.risk_tier === "green") {
      setDeployPhase("deploying");
    }
  }, []);

  if (loading || !scan) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const isGreen = scan.risk_tier === "green";
  const scanDone = scan.status === "complete" || scan.status === "failed";

  return (
    <div className="max-w-4xl space-y-6">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-gray-400 dark:text-slate-500 hover:text-gray-700 dark:hover:text-slate-300 transition-colors"
      >
        <ArrowLeft size={14} />
        Back
      </button>

      {/* Header */}
      <div className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
              {app?.name ?? "Scan Report"}
            </h1>
            {app?.description && (
              <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">{app.description}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-3">
              <StatusBadge status={scan.status} />
              <RiskBadge tier={scan.risk_tier} score={scan.risk_score} />
            </div>
          </div>
          <div className="text-right text-xs text-gray-400 dark:text-slate-600 space-y-1">
            {scan.commit_sha && (
              <p>
                Commit:{" "}
                <code className="text-gray-500 dark:text-slate-400">{scan.commit_sha.slice(0, 8)}</code>
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

      <ScanStream scanId={scanId} initialScan={scan} onComplete={handleScanComplete} />

      {/* Green-tier: show deployment phase stepper */}
      {scanDone && isGreen && (
        <DeploymentStepper phase={deployPhase} deployment={deployment} />
      )}

      {/* Non-green: awaiting human review */}
      {scanDone && !isGreen && scan.status === "complete" && (
        <div className="rounded-lg border border-amber-200 dark:border-amber-800/40 bg-amber-50 dark:bg-amber-900/10 p-4 text-sm text-amber-700 dark:text-amber-400">
          This scan requires human review before the app can be deployed.
          An approver has been notified.
        </div>
      )}
    </div>
  );
}

function DeploymentStepper({
  phase,
  deployment,
}: {
  phase: DeployPhase;
  deployment: Deployment | null;
}) {
  const steps: { label: string; phase: DeployPhase | "scan" }[] = [
    { label: "Scan complete", phase: "scan" },
    { label: "Deploying", phase: "deploying" },
    { label: "Live", phase: "live" },
  ];

  const isLive = phase === "live";
  const isFailed = phase === "failed";
  const activeIndex = isLive ? 2 : 1;

  return (
    <div className="rounded-xl border border-emerald-200 dark:border-emerald-800/40 bg-emerald-50 dark:bg-emerald-900/10 p-6">
      {/* Step indicators */}
      <div className="flex items-center gap-0 mb-6">
        {steps.map((step, i) => {
          const done = i < activeIndex || isLive;
          const active = i === activeIndex && !isLive;
          return (
            <div key={step.label} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors ${
                    done
                      ? "border-emerald-500 bg-emerald-500 dark:border-emerald-400 dark:bg-emerald-400"
                      : active
                      ? "border-indigo-500 bg-white dark:bg-slate-900"
                      : "border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                  }`}
                >
                  {done ? (
                    <CheckCircle size={14} className="text-white dark:text-slate-900" />
                  ) : active ? (
                    <Loader2 size={14} className="text-indigo-500 animate-spin" />
                  ) : (
                    <span className="text-xs text-gray-400 dark:text-slate-600">{i + 1}</span>
                  )}
                </div>
                <span
                  className={`text-xs font-medium whitespace-nowrap ${
                    done
                      ? "text-emerald-700 dark:text-emerald-400"
                      : active
                      ? "text-indigo-600 dark:text-indigo-400"
                      : "text-gray-400 dark:text-slate-600"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div
                  className={`flex-1 h-px mx-2 mb-5 transition-colors ${
                    i < activeIndex || phase === "live"
                      ? "bg-emerald-400 dark:bg-emerald-600"
                      : "bg-gray-200 dark:bg-slate-800"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Status text / CTA */}
      {phase === "deploying" && (
        <p className="text-sm text-emerald-700 dark:text-emerald-400">
          Green tier — automatically approved. Spinning up your container…
        </p>
      )}

      {phase === "live" && deployment?.public_url && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
              Your app is live!
            </p>
            <p className="mt-0.5 text-xs text-emerald-600/70 dark:text-emerald-500">
              {deployment.public_url}
            </p>
          </div>
          <a
            href={deployment.public_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 transition-colors shadow-sm shrink-0"
          >
            <ExternalLink size={14} />
            Open App
          </a>
        </div>
      )}

      {isFailed && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Deployment failed. Check the Deployments page for logs.
        </p>
      )}
    </div>
  );
}
