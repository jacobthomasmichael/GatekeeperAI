"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "dark" | "light" | "system";
type Resolved = "dark" | "light";

interface ThemeCtx {
  theme: Theme;
  resolved: Resolved;
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "system", resolved: "dark", toggle: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("system");
  const [resolved, setResolved] = useState<Resolved>("dark");

  useEffect(() => {
    const saved = (localStorage.getItem("gka_theme") as Theme) ?? "system";
    setTheme(saved);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const isDark = theme === "dark" || (theme === "system" && mq.matches);
      document.documentElement.classList.toggle("dark", isDark);
      setResolved(isDark ? "dark" : "light");
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  function toggle() {
    const next = resolved === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("gka_theme", next);
  }

  return <Ctx.Provider value={{ theme, resolved, toggle }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
