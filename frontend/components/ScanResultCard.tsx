import clsx from "clsx";
import { CheckCircle, AlertTriangle, AlertOctagon, Info, ShieldAlert } from "lucide-react";
import type { ScanResult } from "@/lib/api";

const SCANNER_LABELS: Record<string, string> = {
  secrets: "Secrets",
  dependencies: "Dependencies",
  egress: "Egress URLs",
  pii: "PII Detection",
  llm: "AI Analysis",
};

const SEV_CONFIG: Record<string, { label: string; bar: string; text: string; icon: React.ReactNode }> = {
  critical: {
    label: "Critical",
    bar: "bg-critical-600",
    text: "text-critical-700 dark:text-critical-400",
    icon: <AlertOctagon size={13} />,
  },
  high: {
    label: "High",
    bar: "bg-critical-400",
    text: "text-critical-600 dark:text-critical-400",
    icon: <AlertTriangle size={13} />,
  },
  medium: {
    label: "Medium",
    bar: "bg-warn-500",
    text: "text-warn-800 dark:text-warn-400",
    icon: <AlertTriangle size={13} />,
  },
  low: {
    label: "Low",
    bar: "bg-signal-400",
    text: "text-signal-700 dark:text-signal-400",
    icon: <Info size={13} />,
  },
  none: {
    label: "Clean",
    bar: "bg-good-400",
    text: "text-good-700 dark:text-good-400",
    icon: <CheckCircle size={13} />,
  },
  info: {
    label: "Info",
    bar: "bg-slate-400",
    text: "text-slate-500 dark:text-slate-400",
    icon: <Info size={13} />,
  },
};

// ── Per-scanner finding renderers ─────────────────────────────────────────────

function SecretsFindings({ findings }: { findings: Record<string, unknown> }) {
  const items = (findings.items as Array<{ type: string; file: string; line: number; is_verified: boolean }>) ?? [];
  if (items.length === 0) return <p className="text-xs text-good-600 dark:text-good-400">No secrets or credentials detected.</p>;
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2">
          <ShieldAlert size={13} className="mt-0.5 shrink-0 text-critical-500" />
          <div className="min-w-0">
            <p className="text-xs font-medium text-slate-800 dark:text-slate-200">{item.type}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-mono truncate">
              {item.file}{item.line ? `:${item.line}` : ""}
              {item.is_verified && <span className="ml-1.5 text-critical-500 font-sans">· verified live</span>}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function DependencyFindings({ findings }: { findings: Record<string, unknown> }) {
  if (findings.note) return <p className="text-xs text-slate-400 dark:text-slate-500">{findings.note as string}</p>;
  const items = (findings.items as Array<{ package: string; version?: string; severity: string; cve?: string; via: string[] }>) ?? [];
  if (items.length === 0) return <p className="text-xs text-good-600 dark:text-good-400">No known vulnerabilities found.</p>;
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className={clsx("mt-0.5 shrink-0 text-xs font-semibold uppercase tracking-wide", SEV_CONFIG[item.severity]?.text ?? "text-slate-400")}>
            {item.severity.slice(0, 4)}
          </span>
          <div className="min-w-0">
            <p className="text-xs font-medium text-slate-800 dark:text-slate-200">
              {item.package}{item.version ? `@${item.version}` : ""}
              {item.cve && <code className="ml-1.5 text-slate-400 dark:text-slate-500 text-[10px]">{item.cve}</code>}
            </p>
            {item.via?.length > 0 && (
              <p className="text-xs text-slate-500 dark:text-slate-400">{item.via.filter(Boolean).join(", ")}</p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function EgressFindings({ findings }: { findings: Record<string, unknown> }) {
  const external = (findings.external_urls as string[]) ?? [];
  const unknown = (findings.unknown_urls as string[]) ?? [];
  if (external.length === 0 && unknown.length === 0) {
    return <p className="text-xs text-good-600 dark:text-good-400">No external network egress detected.</p>;
  }
  return (
    <div className="space-y-2">
      {external.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">External</p>
          <ul className="space-y-1">
            {external.map((url, i) => (
              <li key={i} className="text-xs font-mono text-slate-700 dark:text-slate-300 truncate">{url}</li>
            ))}
          </ul>
        </div>
      )}
      {unknown.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-warn-700 mb-1">Unrecognized hosts</p>
          <ul className="space-y-1">
            {unknown.map((url, i) => (
              <li key={i} className="text-xs font-mono text-warn-800 dark:text-warn-300 truncate">{url}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const PII_LABELS: Record<string, string> = {
  credit_card: "Credit card numbers",
  ssn: "Social Security numbers",
  email: "Email addresses",
  phone: "Phone numbers",
  passport: "Passport numbers",
  bank_account: "Bank account numbers",
  api_key: "API keys",
  private_key: "Private keys",
};

function PiiFindings({ findings }: { findings: Record<string, unknown> }) {
  const categories = (findings.categories as string[]) ?? [];
  const files = (findings.files as Record<string, string[]>) ?? {};
  const fileList = Object.entries(files);
  if (categories.length === 0) return <p className="text-xs text-good-600 dark:text-good-400">No PII patterns detected.</p>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {categories.map((cat) => (
          <span key={cat} className="inline-block rounded-full bg-warn-50 dark:bg-warn-950/40 border border-warn-200 dark:border-warn-800/40 px-2 py-0.5 text-xs text-warn-800 dark:text-warn-300">
            {PII_LABELS[cat] ?? cat}
          </span>
        ))}
      </div>
      {fileList.length > 0 && (
        <ul className="space-y-0.5">
          {fileList.slice(0, 4).map(([file]) => (
            <li key={file} className="text-xs font-mono text-slate-500 dark:text-slate-400 truncate">{file}</li>
          ))}
          {fileList.length > 4 && (
            <li className="text-xs text-slate-400 dark:text-slate-500">+{fileList.length - 4} more files</li>
          )}
        </ul>
      )}
    </div>
  );
}

function LlmFindings({ findings }: { findings: Record<string, unknown> }) {
  const description = findings.description as string | undefined;
  const flags = (findings.risk_flags as string[]) ?? [];
  const capabilities = (findings.capabilities as string[]) ?? [];
  const intentMatch = findings.intent_match as boolean | undefined;
  const skipped = description?.toLowerCase().includes("skipped");

  if (skipped) return <p className="text-xs text-slate-400 dark:text-slate-500">{description}</p>;

  return (
    <div className="space-y-2">
      {description && <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{description}</p>}
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {flags.map((flag) => (
            <span key={flag} className="inline-block rounded-full bg-critical-50 dark:bg-critical-950/40 border border-critical-200 dark:border-critical-800/40 px-2 py-0.5 text-xs text-critical-700 dark:text-critical-300">
              {flag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
      {capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {capabilities.map((cap) => (
            <span key={cap} className="inline-block rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-400">
              {cap.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
      {intentMatch === false && (
        <p className="text-xs text-warn-800 dark:text-warn-400 font-medium">⚠ App behaviour may not match its stated description.</p>
      )}
    </div>
  );
}

function FindingsBody({ result }: { result: ScanResult }) {
  const f = result.findings;
  switch (result.scanner_name) {
    case "secrets":      return <SecretsFindings findings={f} />;
    case "dependencies": return <DependencyFindings findings={f} />;
    case "egress":       return <EgressFindings findings={f} />;
    case "pii":          return <PiiFindings findings={f} />;
    case "llm":          return <LlmFindings findings={f} />;
    default:
      return Object.keys(f).length > 0
        ? <pre className="text-xs text-slate-500 dark:text-slate-400 whitespace-pre-wrap break-all overflow-auto max-h-32">{JSON.stringify(f, null, 2)}</pre>
        : null;
  }
}

// ── Public component ──────────────────────────────────────────────────────────

export default function ScanResultCard({ result }: { result: ScanResult }) {
  const sev = SEV_CONFIG[result.severity] ?? SEV_CONFIG.info;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
      {/* Severity bar */}
      <div className={clsx("h-1 w-full", sev.bar)} />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-slate-900 dark:text-white">
            {SCANNER_LABELS[result.scanner_name] ?? result.scanner_name}
          </span>
          <span className={clsx("flex items-center gap-1 text-xs font-medium", sev.text)}>
            {sev.icon}
            {sev.label}
          </span>
        </div>

        {/* Findings */}
        <FindingsBody result={result} />

        {/* Duration */}
        <p className="mt-3 text-[10px] text-slate-300 dark:text-slate-700">{result.duration_ms}ms</p>
      </div>
    </div>
  );
}
