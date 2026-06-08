import clsx from "clsx";

interface Props {
  status: string;
}

const STYLES: Record<string, string> = {
  pending_scan: "bg-slate-800 text-slate-300 border-slate-700",
  scanning: "bg-blue-900/40 text-blue-400 border-blue-700/50",
  running: "bg-blue-900/40 text-blue-400 border-blue-700/50",
  complete: "bg-slate-800 text-slate-300 border-slate-700",
  approved: "bg-emerald-900/40 text-emerald-400 border-emerald-700/50",
  deployed: "bg-emerald-900/40 text-emerald-400 border-emerald-700/50",
  awaiting_approval: "bg-amber-900/40 text-amber-400 border-amber-700/50",
  rejected: "bg-red-900/40 text-red-400 border-red-700/50",
  failed: "bg-red-900/40 text-red-400 border-red-700/50",
  stopped: "bg-slate-800 text-slate-400 border-slate-700",
};

const LABELS: Record<string, string> = {
  pending_scan: "Pending",
  awaiting_approval: "Awaiting Approval",
};

export default function StatusBadge({ status }: Props) {
  const label = LABELS[status] ?? status.replace(/_/g, " ");
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        STYLES[status] ?? "bg-slate-800 text-slate-400 border-slate-700"
      )}
    >
      {label}
    </span>
  );
}
