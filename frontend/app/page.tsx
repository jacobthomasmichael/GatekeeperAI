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
        // If status check fails, fall back to login
        router.replace("/login");
      });
  }, [router]);

  return null;
}
