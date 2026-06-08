"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import clsx from "clsx";
import {
  LayoutDashboard,
  CheckSquare,
  BarChart3,
  LogOut,
  Shield,
  PlusCircle,
  Boxes,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  roles?: string[];
}

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "My Apps",
    icon: <LayoutDashboard size={18} />,
  },
  {
    href: "/dashboard/submit",
    label: "Submit App",
    icon: <PlusCircle size={18} />,
  },
  {
    href: "/approvals",
    label: "Approvals",
    icon: <CheckSquare size={18} />,
    roles: ["approver", "admin"],
  },
  {
    href: "/deployments",
    label: "Deployments",
    icon: <Boxes size={18} />,
    roles: ["approver", "admin"],
  },
  {
    href: "/admin",
    label: "Admin Stats",
    icon: <BarChart3 size={18} />,
    roles: ["admin"],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const visibleNav = NAV.filter(
    (item) =>
      !item.roles ||
      (user && (item.roles.includes(user.role) || user.role === "admin"))
  );

  return (
    <aside className="flex h-screen w-60 flex-col bg-slate-900 border-r border-slate-800">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-800">
        <Shield size={20} className="text-indigo-400" />
        <span className="font-semibold text-white tracking-tight">
          GatekeeperAI
        </span>
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
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-slate-800 p-4">
        <div className="mb-3 px-1">
          <p className="text-xs font-medium text-white truncate">
            {user?.username}
          </p>
          <p className="text-xs text-slate-500 truncate">{user?.email}</p>
          <span className="mt-1 inline-block rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300 capitalize">
            {user?.role}
          </span>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
