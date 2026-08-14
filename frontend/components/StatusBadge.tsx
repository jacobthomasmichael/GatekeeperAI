import clsx from "clsx";

interface Props {
  status: string;
}

const STYLES: Record<string, string> = {
  pending_scan:       "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700",
  scanning:           "bg-signal-50 dark:bg-signal-900/40 text-signal-700 dark:text-signal-400 border-signal-200 dark:border-signal-700/50",
  running:            "bg-signal-50 dark:bg-signal-900/40 text-signal-700 dark:text-signal-400 border-signal-200 dark:border-signal-700/50",
  complete:           "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700",
  approved:           "bg-good-50 dark:bg-good-900/40 text-good-700 dark:text-good-400 border-good-200 dark:border-good-700/50",
  deployed:           "bg-good-50 dark:bg-good-900/40 text-good-700 dark:text-good-400 border-good-200 dark:border-good-700/50",
  awaiting_approval:  "bg-warn-50 dark:bg-warn-900/40 text-warn-800 dark:text-warn-400 border-warn-200 dark:border-warn-700/50",
  rejected:           "bg-critical-50 dark:bg-critical-900/40 text-critical-700 dark:text-critical-400 border-critical-200 dark:border-critical-700/50",
  failed:             "bg-critical-50 dark:bg-critical-900/40 text-critical-700 dark:text-critical-400 border-critical-200 dark:border-critical-700/50",
  stopped:            "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700",
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
        STYLES[status] ?? "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700"
      )}
    >
      {label}
    </span>
  );
}
