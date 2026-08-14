"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/components/ThemeProvider";
import clsx from "clsx";
import {
  LayoutDashboard,
  CheckSquare,
  BarChart3,
  LogOut,
  Shield,
  PlusCircle,
  Boxes,
  Sun,
  Moon,
  Settings,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  roles?: string[];
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "My Apps", icon: <LayoutDashboard size={18} /> },
  { href: "/dashboard/submit", label: "Submit App", icon: <PlusCircle size={18} /> },
  { href: "/approvals", label: "Approvals", icon: <CheckSquare size={18} />, roles: ["approver", "admin"] },
  { href: "/deployments", label: "Deployments", icon: <Boxes size={18} />, roles: ["approver", "admin"] },
  { href: "/admin", label: "Admin Stats", icon: <BarChart3 size={18} />, roles: ["admin"] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { resolved, toggle } = useTheme();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const visibleNav = NAV.filter(
    (item) => !item.roles || (user && (item.roles.includes(user.role) || user.role === "admin"))
  );

  return (
    <aside className="flex h-screen w-60 flex-col bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800">
      {/* Logo */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Shield size={20} className="text-signal-600 dark:text-signal-400" />
          <span className="font-semibold text-slate-900 dark:text-white tracking-tight">
            GatekeeperAI
          </span>
        </div>
        <button
          onClick={toggle}
          title={resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-md p-1.5 text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
        >
          {resolved === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {visibleNav.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-signal-600 text-white"
                  : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-slate-200 dark:border-slate-800 p-4">
        <div className="mb-3 flex items-center gap-2.5 px-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-signal-50 text-signal-700 dark:bg-signal-950/40 dark:text-signal-400">
            <span className="text-xs font-bold uppercase">{user?.username?.slice(0, 2)}</span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-slate-900 dark:text-white truncate">
              {user?.username}
            </p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 truncate">{user?.email}</p>
            <span className="mt-0.5 inline-block rounded-full bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:text-slate-300 capitalize">
              {user?.role}
            </span>
          </div>
        </div>
        <Link
          href="/account"
          className={clsx(
            "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors mb-0.5",
            pathname === "/account"
              ? "bg-signal-600 text-white"
              : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
          )}
        >
          <Settings size={16} />
          Account
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
