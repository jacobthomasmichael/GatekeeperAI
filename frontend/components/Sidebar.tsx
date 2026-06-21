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
    <aside className="flex h-screen w-60 flex-col bg-white dark:bg-slate-900 border-r border-gray-200 dark:border-slate-800">
      {/* Logo */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-gray-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Shield size={20} className="text-indigo-500 dark:text-indigo-400" />
          <span className="font-semibold text-gray-900 dark:text-white tracking-tight">
            GatekeeperAI
          </span>
        </div>
        <button
          onClick={toggle}
          title={resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-md p-1.5 text-gray-400 dark:text-slate-500 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-600 dark:hover:text-slate-300 transition-colors"
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
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-white"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-gray-200 dark:border-slate-800 p-4">
        <div className="mb-3 px-1">
          <p className="text-xs font-medium text-gray-900 dark:text-white truncate">
            {user?.username}
          </p>
          <p className="text-xs text-gray-400 dark:text-slate-500 truncate">{user?.email}</p>
          <span className="mt-1 inline-block rounded-full bg-gray-100 dark:bg-slate-700 px-2 py-0.5 text-xs text-gray-600 dark:text-slate-300 capitalize">
            {user?.role}
          </span>
        </div>
        <Link
          href="/account"
          className={clsx(
            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors mb-0.5",
            pathname === "/account"
              ? "bg-indigo-600 text-white"
              : "text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-white"
          )}
        >
          <Settings size={16} />
          Account
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
