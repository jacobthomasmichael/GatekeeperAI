import clsx from "clsx";

interface Props {
  tier: string | null;
  score?: number | null;
  size?: "sm" | "md" | "lg";
}

const COLORS: Record<string, string> = {
  green:  "bg-good-50 dark:bg-good-900/40 text-good-700 dark:text-good-400 border-good-200 dark:border-good-700/50",
  yellow: "bg-warn-50 dark:bg-warn-900/40 text-warn-800 dark:text-warn-400 border-warn-200 dark:border-warn-700/50",
  red:    "bg-critical-50 dark:bg-critical-900/40 text-critical-700 dark:text-critical-400 border-critical-200 dark:border-critical-700/50",
};

export default function RiskBadge({ tier, score, size = "md" }: Props) {
  if (!tier) return <span className="text-slate-400 dark:text-slate-500 text-sm">—</span>;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium capitalize",
        COLORS[tier] ?? "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base"
      )}
    >
      <span
        className={clsx(
          "rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          tier === "green"  && "bg-good-500 dark:bg-good-400",
          tier === "yellow" && "bg-warn-500 dark:bg-warn-400",
          tier === "red"    && "bg-critical-500 dark:bg-critical-400",
          !["green", "yellow", "red"].includes(tier) && "bg-slate-400 dark:bg-slate-400"
        )}
      />
      {tier}
      {score !== undefined && score !== null && (
        <span className="opacity-70">({score})</span>
      )}
    </span>
  );
}
