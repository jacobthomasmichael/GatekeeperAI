"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { appsApi, ApiError } from "@/lib/api";

export default function SubmitPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await appsApi.create(name.trim(), description.trim());
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create app");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Submit an App</h1>
        <p className="mt-1 text-sm text-gray-400 dark:text-slate-500">
          Register a new app. You&apos;ll receive a git remote URL to push your code to.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5"
      >
        {error && (
          <div className="rounded-md bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/40 px-3 py-2 text-sm text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700 dark:text-slate-300">
            App name <span className="text-red-500 dark:text-red-400">*</span>
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="my-streamlit-app"
            pattern="[a-zA-Z0-9_\-]+"
            title="Letters, numbers, hyphens, and underscores only"
            className="w-full rounded-md border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <p className="text-xs text-gray-400 dark:text-slate-600">Letters, numbers, hyphens, underscores</p>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700 dark:text-slate-300">
            Description <span className="text-red-500 dark:text-red-400">*</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            rows={4}
            placeholder="Describe what this app does, its purpose, and any external services it connects to..."
            className="w-full rounded-md border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
          />
          <p className="text-xs text-gray-400 dark:text-slate-600">
            This is shown to approvers and used by the AI scanner to evaluate intent.
          </p>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating..." : "Create App"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-gray-300 dark:border-slate-700 px-4 py-2 text-sm text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>

      <div className="rounded-lg border border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-4 text-sm text-gray-400 dark:text-slate-500 space-y-2">
        <p className="font-medium text-gray-600 dark:text-slate-400">What happens next?</p>
        <ol className="list-decimal list-inside space-y-1">
          <li>A bare git repository is created for your app</li>
          <li>Push your code with <code className="text-gray-700 dark:text-slate-300">git push</code></li>
          <li>A security scan runs automatically on every push</li>
          <li>Green tier apps auto-approve; Yellow/Red go to human review</li>
          <li>Approved apps deploy to an isolated container</li>
        </ol>
      </div>
    </div>
  );
}
