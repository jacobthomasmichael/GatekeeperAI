import clsx from "clsx";

interface Props {
  tier: string | null;
  score?: number | null;
  size?: "sm" | "md" | "lg";
}

const COLORS: Record<string, string> = {
  green:  "bg-emerald-50 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-700/50",
  yellow: "bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-700/50",
  red:    "bg-red-50 dark:bg-red-900/40 text-red-700 dark:text-red-400 border-red-200 dark:border-red-700/50",
};

export default function RiskBadge({ tier, score, size = "md" }: Props) {
  if (!tier) return <span className="text-gray-400 dark:text-slate-500 text-sm">—</span>;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium capitalize",
        COLORS[tier] ?? "bg-gray-100 dark:bg-slate-800 text-gray-500 dark:text-slate-400 border-gray-200 dark:border-slate-700",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base"
      )}
    >
      <span
        className={clsx(
          "rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          tier === "green"  && "bg-emerald-500 dark:bg-emerald-400",
          tier === "yellow" && "bg-amber-500 dark:bg-amber-400",
          tier === "red"    && "bg-red-500 dark:bg-red-400",
          !["green", "yellow", "red"].includes(tier) && "bg-gray-400 dark:bg-slate-400"
        )}
      />
      {tier}
      {score !== undefined && score !== null && (
        <span className="opacity-70">({score})</span>
      )}
    </span>
  );
}
