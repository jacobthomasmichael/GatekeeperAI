"use client";

import { useRef, useState, FormEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { appsApi, ApiError } from "@/lib/api";
import {
  UploadCloud,
  FileArchive,
  X,
  Loader2,
  Shield,
  Users,
  CheckCircle2,
  ChevronDown,
} from "lucide-react";

export default function SubmitPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Set once appsApi.create() succeeds. If a subsequent upload fails, we keep
  // this around so retrying doesn't try to create the app a second time.
  const [createdAppId, setCreatedAppId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // App names are used as slugs (container names, URL paths) — the backend requires
  // lowercase alphanumeric + hyphens, 3-50 chars, no leading/trailing hyphen
  // (^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$). Normalize as the user types instead of
  // letting them hit that error after submitting.
  function normalizeName(v: string) {
    return v.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/-{2,}/g, "-");
  }

  function pickFile(f: File | null | undefined) {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".zip")) {
      setError("Please choose a .zip file.");
      return;
    }
    setError("");
    setFile(f);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      let appId = createdAppId;
      if (!appId) {
        const app = await appsApi.create(name.trim(), description.trim());
        appId = app.id;
        setCreatedAppId(appId);
      }
      if (file) {
        const { scan_id } = await appsApi.uploadZip(appId, file);
        router.push(`/dashboard/scans/${scan_id}`);
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const locked = !!createdAppId; // app record already created — retrying an upload, not resubmitting details

  return (
    <div className="max-w-4xl">
      <div className="max-w-xl">
        <p className="text-[11px] font-bold uppercase tracking-wider text-signal-700 dark:text-signal-400">
          New submission
        </p>
        <h1 className="mt-1 text-[28px] font-bold tracking-tight text-slate-900 dark:text-white">
          Submit an app
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-slate-500 dark:text-slate-400">
          Tell us what it does. We&apos;ll scan it, route it to a reviewer if needed, and deploy it
          once it&apos;s cleared.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mt-8 grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.15fr_0.85fr]"
      >
        {/* Main panel */}
        <div className="rounded-[22px] border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-900 p-7 shadow-sm">
          {error && (
            <div className="mb-5 rounded-xl border border-critical-200 dark:border-critical-800/50 bg-critical-50 dark:bg-critical-950/30 px-4 py-3 text-sm text-critical-700 dark:text-critical-300">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="fname" className="text-xs font-bold text-slate-600 dark:text-slate-300">
              Name
            </label>
            <input
              id="fname"
              value={name}
              onChange={(e) => setName(normalizeName(e.target.value))}
              required
              disabled={locked}
              placeholder="snake"
              minLength={3}
              maxLength={50}
              pattern={"[a-z0-9][a-z0-9\\-]{1,48}[a-z0-9]"}
              title="3-50 lowercase letters, numbers, and hyphens — can't start or end with a hyphen"
              className="w-full rounded-xl border-[1.5px] border-transparent bg-slate-50 dark:bg-slate-800 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 outline-none transition-colors focus:border-signal-600 dark:focus:border-signal-400 focus:bg-white dark:focus:bg-slate-900 disabled:opacity-60"
            />
            <p className="text-[11.5px] text-slate-400 dark:text-slate-500">
              Lowercase letters, numbers, and hyphens — this becomes part of your app&apos;s URL.
            </p>
          </div>

          <div className="mt-5 space-y-1.5">
            <label htmlFor="fdesc" className="text-xs font-bold text-slate-600 dark:text-slate-300">
              What does it do?
            </label>
            <textarea
              id="fdesc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              disabled={locked}
              rows={3}
              placeholder="A small internal game with a persistent leaderboard, used as our onboarding demo."
              className="w-full resize-none rounded-xl border-[1.5px] border-transparent bg-slate-50 dark:bg-slate-800 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 outline-none transition-colors focus:border-signal-600 dark:focus:border-signal-400 focus:bg-white dark:focus:bg-slate-900 disabled:opacity-60"
            />
            <p className="text-[11.5px] text-slate-400 dark:text-slate-500">
              Shown to reviewers, and used by the scanner to check the app does what you say it does.
            </p>
          </div>

          {/* Dropzone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
            className={`mt-6 cursor-pointer rounded-2xl border-2 border-dashed px-5 py-7 text-center transition-colors ${
              dragOver
                ? "border-signal-500 bg-signal-50 dark:bg-signal-950/30"
                : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 hover:border-signal-400 hover:bg-signal-50/60 dark:hover:bg-signal-950/20"
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
            {file ? (
              <>
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-white dark:bg-slate-900 text-good-600 dark:text-good-400 shadow-sm">
                  <FileArchive size={20} />
                </div>
                <p className="mt-3 text-sm font-bold text-slate-800 dark:text-white">{file.name}</p>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileRef.current) fileRef.current.value = "";
                  }}
                  className="mt-1.5 inline-flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-critical-600 dark:hover:text-critical-400"
                >
                  <X size={12} /> Remove
                </button>
              </>
            ) : (
              <>
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-white dark:bg-slate-900 text-signal-600 dark:text-signal-400 shadow-sm">
                  <UploadCloud size={20} />
                </div>
                <p className="mt-3 text-sm font-bold text-slate-800 dark:text-white">Drag your app here</p>
                <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                  or browse for a .zip — no git required
                </p>
              </>
            )}
          </div>

          <details className="group mt-4">
            <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-semibold text-slate-500 hover:text-signal-700 dark:text-slate-400 dark:hover:text-signal-400">
              Prefer pushing with git?
              <ChevronDown size={13} className="transition-transform group-open:rotate-180" />
            </summary>
            <div className="mt-2.5 rounded-xl bg-slate-800 px-4 py-3 dark:bg-slate-950">
              <p className="text-xs text-slate-300 dark:text-slate-400">
                {locked
                  ? "Your push URL is on the dashboard, under this app's card."
                  : "You'll get a push URL here once the app is created — or just drop a zip above, no git required."}
              </p>
            </div>
          </details>

          <button
            type="submit"
            disabled={submitting || (!locked && (!name.trim() || !description.trim())) || (locked && !file)}
            className="mt-7 flex w-full items-center justify-center gap-2 rounded-full bg-signal-600 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-signal-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                {file ? "Creating & uploading…" : "Creating…"}
              </>
            ) : locked ? (
              <>
                <UploadCloud size={15} />
                Try upload again
              </>
            ) : (
              <>
                <CheckCircle2 size={15} />
                {file ? "Create app & scan" : "Create app"}
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => (locked ? router.push("/dashboard") : router.back())}
            className="mt-3 w-full text-center text-xs font-semibold text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
          >
            {locked ? "Skip for now — go to dashboard" : "Cancel"}
          </button>
        </div>

        {/* Side reassurance panel */}
        <div className="rounded-[22px] border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <p className="text-[11px] font-bold uppercase tracking-wider text-signal-700 dark:text-signal-400">
            What happens next
          </p>
          <div className="mt-4 space-y-4">
            <Step
              icon={<Shield size={13} />}
              title="We scan it"
              body="Secrets, dependencies, network calls, personal data, and an AI review — usually under a minute."
            />
            <Step
              icon={<Users size={13} />}
              title="Clean apps deploy automatically"
              body="Anything flagged goes to a reviewer first, with a deadline."
            />
            <Step
              icon={<CheckCircle2 size={13} />}
              title="You get a live URL"
              body="Access-gated by default — only you, until you choose to share it."
            />
          </div>
        </div>
      </form>
    </div>
  );
}

function Step({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-signal-50 text-signal-700 dark:bg-signal-950/40 dark:text-signal-400">
        {icon}
      </div>
      <div>
        <p className="text-[13px] font-bold text-slate-800 dark:text-white">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{body}</p>
      </div>
    </div>
  );
}
