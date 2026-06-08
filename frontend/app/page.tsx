"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Root() {
  const router = useRouter();
  useEffect(() => {
    const token = localStorage.getItem("gka_token");
    router.replace(token ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
