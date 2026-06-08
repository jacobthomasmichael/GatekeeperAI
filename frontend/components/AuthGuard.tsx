"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

interface Props {
  children: React.ReactNode;
  requireRole?: "ic" | "approver" | "admin";
}

export default function AuthGuard({ children, requireRole }: Props) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (requireRole && user.role !== requireRole && user.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [user, loading, requireRole, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-600 border-t-indigo-500" />
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}
