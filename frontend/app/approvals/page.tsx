"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { approvalsApi, type ApprovalDetail } from "@/lib/api";
import RiskBadge from "@/components/RiskBadge";
import { Clock, CheckCircle, XCircle, Zap } from "lucide-react";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalDetail[]>([]);
  const [pendingOnly, setPendingOnly] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    approvalsApi.list(pendingOnly).then((list) => {
      setApprovals(list);
      setLoading(false);
    });
  }, [pendingOnly]);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Approval Queue</h1>
          <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
            Review and approve or reject flagged app submissions
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={pendingOnly}
            onChange={(e) => setPendingOnly(e.target.checked)}
            className="rounded border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-indigo-600"
          />
          Pending only
        </label>
      </div>

      {loading && (
        <div className="flex h-32 items-center justify-center">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-indigo-500" />
        </div>
      )}

      {!loading && approvals.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900/50 p-12 text-center">
          <CheckCircle size={32} className="mx-auto text-emerald-500 dark:text-emerald-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-600 dark:text-slate-300">All clear</h3>
          <p className="text-sm text-gray-400 dark:text-slate-500 mt-1">No pending approvals.</p>
        </div>
      )}

      <div className="space-y-3">
        {approvals.map((a) => {
          const overdue = !a.decision && new Date(a.sla_deadline) < new Date();
          return (
            <Link
              key={a.id}
              href={`/approvals/${a.id}`}
              className="block rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 hover:border-gray-300 dark:hover:border-slate-700 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-medium text-gray-900 dark:text-white">{a.app_name}</span>
                    <RiskBadge tier={a.risk_tier} score={a.risk_score} size="sm" />
                    {a.is_expedited && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-indigo-200 dark:border-indigo-700/50 bg-indigo-50 dark:bg-indigo-900/30 px-2 py-0.5 text-xs text-indigo-600 dark:text-indigo-400">
                        <Zap size={10} />
                        Expedited · Update
                      </span>
                    )}
                    {a.scan_type === "update" && !a.is_expedited && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-400">
                        Update
                      </span>
                    )}
                    {overdue && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-red-200 dark:border-red-700/50 bg-red-50 dark:bg-red-900/30 px-2 py-0.5 text-xs text-red-600 dark:text-red-400">
                        <Clock size={10} />
                        Overdue
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-gray-400 dark:text-slate-500 line-clamp-1">
                    {a.app_description}
                  </p>
                  <div className="mt-2 text-xs text-gray-300 dark:text-slate-600">
                    SLA: {new Date(a.sla_deadline).toLocaleString()}
                  </div>
                </div>

                <div className="shrink-0">
                  {a.decision === null ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/30 px-2.5 py-1 text-xs text-amber-700 dark:text-amber-400">
                      <Clock size={12} />
                      Pending
                    </span>
                  ) : a.decision === "approved" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 dark:border-emerald-700/50 bg-emerald-50 dark:bg-emerald-900/30 px-2.5 py-1 text-xs text-emerald-700 dark:text-emerald-400">
                      <CheckCircle size={12} />
                      Approved
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 dark:border-red-700/50 bg-red-50 dark:bg-red-900/30 px-2.5 py-1 text-xs text-red-700 dark:text-red-400">
                      <XCircle size={12} />
                      Rejected
                    </span>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
