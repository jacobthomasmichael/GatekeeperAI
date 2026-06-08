"use client";

import { useEffect, useState } from "react";
import { approvalsApi, deploymentsApi, appsApi, type ApprovalStats, type Deployment, type AppSubmission } from "@/lib/api";
import { CheckCircle, XCircle, Clock, AlertTriangle, Boxes, Layers } from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import RiskBadge from "@/components/RiskBadge";

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className={`mb-3 inline-flex rounded-lg p-2 ${color}`}>{icon}</div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-slate-500 mt-0.5">{label}</p>
    </div>
  );
}

export default function AdminPage() {
  const [stats, setStats] = useState<ApprovalStats | null>(null);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [apps, setApps] = useState<AppSubmission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      approvalsApi.stats(),
      deploymentsApi.list(),
      appsApi.list(),
    ]).then(([s, d, a]) => {
      setStats(s);
      setDeployments(d);
      setApps(a);
      setLoading(false);
    });
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-slate-700 border-t-indigo-500" />
      </div>
    );
  }

  const running = deployments.filter((d) => d.status === "running").length;

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Platform-wide metrics</p>
      </div>

      {/* Approval stats */}
      <div>
        <h2 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Approvals
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard
            label="Total"
            value={stats.total}
            icon={<Layers size={16} className="text-slate-400" />}
            color="bg-slate-800"
          />
          <StatCard
            label="Pending"
            value={stats.pending}
            icon={<Clock size={16} className="text-amber-400" />}
            color="bg-amber-900/30"
          />
          <StatCard
            label="Approved"
            value={stats.approved}
            icon={<CheckCircle size={16} className="text-emerald-400" />}
            color="bg-emerald-900/30"
          />
          <StatCard
            label="Rejected"
            value={stats.rejected}
            icon={<XCircle size={16} className="text-red-400" />}
            color="bg-red-900/30"
          />
          <StatCard
            label="Overdue"
            value={stats.overdue}
            icon={<AlertTriangle size={16} className="text-orange-400" />}
            color="bg-orange-900/30"
          />
        </div>
      </div>

      {/* Deployments */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Deployments
          </h2>
          <span className="text-xs text-slate-600">
            {running} running / {deployments.length} total
          </span>
        </div>
        {deployments.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center">
            <Boxes size={28} className="mx-auto text-slate-600 mb-2" />
            <p className="text-sm text-slate-500">No deployments yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {deployments.map((d) => (
              <div
                key={d.id}
                className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {d.container_name ?? d.id.slice(0, 8)}
                  </p>
                  {d.image_tag && (
                    <p className="text-xs text-slate-600 truncate">{d.image_tag}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge status={d.status} />
                  {d.public_url && d.status === "running" && (
                    <a
                      href={d.public_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-indigo-400 hover:underline"
                    >
                      {d.public_url}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* All apps */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            All Apps
          </h2>
          <span className="text-xs text-slate-600">{apps.length} total</span>
        </div>
        <div className="space-y-2">
          {apps.map((app) => (
            <div
              key={app.id}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 flex items-center justify-between gap-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{app.name}</p>
                <p className="text-xs text-slate-600 truncate">{app.description}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <StatusBadge status={app.status} />
                <RiskBadge tier={app.risk_tier} size="sm" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
