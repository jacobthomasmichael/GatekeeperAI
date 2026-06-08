import clsx from "clsx";

interface Props {
  tier: string | null;
  score?: number | null;
  size?: "sm" | "md" | "lg";
}

const COLORS: Record<string, string> = {
  green: "bg-emerald-900/40 text-emerald-400 border-emerald-700/50",
  yellow: "bg-amber-900/40 text-amber-400 border-amber-700/50",
  red: "bg-red-900/40 text-red-400 border-red-700/50",
};

export default function RiskBadge({ tier, score, size = "md" }: Props) {
  if (!tier) return <span className="text-slate-500 text-sm">—</span>;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium capitalize",
        COLORS[tier] ?? "bg-slate-800 text-slate-400 border-slate-700",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base"
      )}
    >
      <span
        className={clsx(
          "rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          tier === "green" && "bg-emerald-400",
          tier === "yellow" && "bg-amber-400",
          tier === "red" && "bg-red-400",
          !["green", "yellow", "red"].includes(tier) && "bg-slate-400"
        )}
      />
      {tier}
      {score !== undefined && score !== null && (
        <span className="opacity-70">({score})</span>
      )}
    </span>
  );
}
