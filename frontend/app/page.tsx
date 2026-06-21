"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function Root() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("gka_token");
    if (token) {
      router.replace("/dashboard");
      return;
    }
    fetch(`${API}/setup/status`)
      .then((r) => r.json())
      .then((json) => {
        router.replace(json.complete ? "/login" : "/setup");
      })
      .catch(() => {
        router.replace("/login");
      });
  }, [router]);

  return (
    <>
      {/* Fallback for users with JavaScript disabled */}
      <noscript>
        <meta httpEquiv="refresh" content="0;url=/login" />
      </noscript>
      {/* Spinner shown while the redirect decision is in flight */}
      <div className="flex h-screen items-center justify-center bg-white dark:bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-indigo-500" />
      </div>
    </>
  );
}
