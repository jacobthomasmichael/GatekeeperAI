"use client";

import { useEffect, useState, FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { approvalsApi, type ApprovalDetail, ApiError } from "@/lib/api";
import RiskBadge from "@/components/RiskBadge";
import { ArrowLeft, CheckCircle, XCircle } from "lucide-react";
import clsx from "clsx";

const SCANNER_LABELS: Record<string, string> = {
  secrets: "Secrets",
  dependencies: "Dependencies",
  egress: "Egress URLs",
  pii: "PII Detection",
  llm: "AI Analysis",
};

const SEV_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-amber-400",
  low: "text-emerald-400",
  none: "text-slate-500",
  info: "text-slate-500",
};

export default function ApprovalDetailPage() {
  const { approvalId } = useParams<{ approvalId: string }>();
  const router = useRouter();
  const [approval, setApproval] = useState<ApprovalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    approvalsApi.get(approvalId).then((a) => {
      setApproval(a);
      setLoading(false);
    });
  }, [approvalId]);

  async function handleDecide(e: FormEvent) {
    e.preventDefault();
    if (!decision) return;
    if (comment.trim().length < 10) {
      setError("Comment must be at least 10 characters.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await approvalsApi.decide(approvalId, decision, comment.trim());
      router.push("/approvals");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit decision");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || !approval) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const decided = approval.decision !== null;

  return (
    <div className="max-w-4xl space-y-6">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition-colors"
      >
        <ArrowLeft size={14} />
        Back to queue
      </button>

      {/* App + scan summary */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-white">{approval.app_name}</h1>
            <p className="mt-1 text-sm text-slate-500">{approval.app_description}</p>
          </div>
          <RiskBadge tier={approval.risk_tier} score={approval.risk_score} size="lg" />
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-slate-500 sm:grid-cols-4">
          <div>
            <span className="block text-slate-400 font-medium mb-0.5">Commit</span>
            <code className="text-slate-300">{approval.commit_sha?.slice(0, 8)}</code>
          </div>
          <div>
            <span className="block text-slate-400 font-medium mb-0.5">SLA Deadline</span>
            {new Date(approval.sla_deadline).toLocaleString()}
          </div>
          <div>
            <span className="block text-slate-400 font-medium mb-0.5">Submitted</span>
            {new Date(approval.created_at).toLocaleString()}
          </div>
          {decided && (
            <div>
              <span className="block text-slate-400 font-medium mb-0.5">Decided</span>
              {new Date(approval.decided_at!).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Scanner results */}
      <div>
        <h2 className="text-sm font-medium text-slate-400 mb-3">Scanner Results</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {approval.scan_results.map((r) => (
            <div
              key={r.id}
              className="rounded-lg border border-slate-800 bg-slate-900 p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm font-medium text-white capitalize">
                  {SCANNER_LABELS[r.scanner_name] ?? r.scanner_name}
                </span>
                <span className={clsx("text-xs font-medium", SEV_COLOR[r.severity] ?? "text-slate-400")}>
                  {r.severity}
                </span>
              </div>
              <div className="text-xs text-slate-600">{r.duration_ms}ms</div>
              {Object.keys(r.findings).length > 0 && (
                <details className="mt-2">
                  <summary className="text-xs text-indigo-400 cursor-pointer select-none">
                    View findings
                  </summary>
                  <pre className="mt-2 text-xs text-slate-400 whitespace-pre-wrap break-all overflow-auto max-h-40">
                    {JSON.stringify(r.findings, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Decision form or result */}
      {decided ? (
        <div
          className={clsx(
            "rounded-xl border p-5",
            approval.decision === "approved"
              ? "border-emerald-800/40 bg-emerald-900/10"
              : "border-red-800/40 bg-red-900/10"
          )}
        >
          <div className="flex items-center gap-2 mb-2">
            {approval.decision === "approved" ? (
              <CheckCircle size={18} className="text-emerald-400" />
            ) : (
              <XCircle size={18} className="text-red-400" />
            )}
            <span
              className={clsx(
                "font-medium capitalize",
                approval.decision === "approved" ? "text-emerald-400" : "text-red-400"
              )}
            >
              {approval.decision}
            </span>
          </div>
          {approval.comment && (
            <p className="text-sm text-slate-400">{approval.comment}</p>
          )}
        </div>
      ) : (
        <form
          onSubmit={handleDecide}
          className="rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-5"
        >
          <h2 className="text-base font-medium text-white">Make a Decision</h2>

          {error && (
            <div className="rounded-md bg-red-900/30 border border-red-700/40 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Decision toggles */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setDecision("approved")}
              className={clsx(
                "flex-1 flex items-center justify-center gap-2 rounded-lg border py-3 text-sm font-medium transition-colors",
                decision === "approved"
                  ? "border-emerald-600 bg-emerald-900/30 text-emerald-400"
                  : "border-slate-700 text-slate-400 hover:border-slate-600 hover:bg-slate-800"
              )}
            >
              <CheckCircle size={16} />
              Approve
            </button>
            <button
              type="button"
              onClick={() => setDecision("rejected")}
              className={clsx(
                "flex-1 flex items-center justify-center gap-2 rounded-lg border py-3 text-sm font-medium transition-colors",
                decision === "rejected"
                  ? "border-red-600 bg-red-900/30 text-red-400"
                  : "border-slate-700 text-slate-400 hover:border-slate-600 hover:bg-slate-800"
              )}
            >
              <XCircle size={16} />
              Reject
            </button>
          </div>

          {/* Comment */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-300">
              Comment <span className="text-red-400">*</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              required
              rows={3}
              placeholder="Explain your decision (min 10 characters)..."
              className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={!decision || submitting}
            className={clsx(
              "rounded-md px-5 py-2 text-sm font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
              decision === "rejected"
                ? "bg-red-700 hover:bg-red-600"
                : "bg-indigo-600 hover:bg-indigo-500"
            )}
          >
            {submitting
              ? "Submitting..."
              : decision
              ? `Submit ${decision}`
              : "Select a decision"}
          </button>
        </form>
      )}
    </div>
  );
}
