"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Chunk load failures and stale Server Action errors happen after a
    // deployment when the browser has a previous build cached. Auto-reload
    // once — if the page still fails after that, show the error UI.
    const isStaleBundle =
      error.message?.includes("Loading chunk") ||
      error.message?.includes("Failed to fetch") ||
      error.message?.includes("dynamically imported module") ||
      error.digest?.startsWith("NEXT_NOT_FOUND");

    if (isStaleBundle) {
      // Only auto-reload if we haven't already tried (prevents reload loops)
      if (!sessionStorage.getItem("gka_error_reloaded")) {
        sessionStorage.setItem("gka_error_reloaded", "1");
        window.location.reload();
      }
    }
  }, [error]);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-6 bg-white dark:bg-slate-950 px-4 text-center">
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-8 max-w-md w-full">
        <p className="text-2xl mb-2">⚠️</p>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Something went wrong
        </h2>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-6">
          This can happen after a platform update. Refreshing the page usually
          fixes it.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => {
              sessionStorage.removeItem("gka_error_reloaded");
              window.location.reload();
            }}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            Refresh page
          </button>
          <button
            onClick={() => {
              sessionStorage.removeItem("gka_error_reloaded");
              reset();
            }}
            className="rounded-md border border-slate-200 dark:border-slate-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    </div>
  );
}
