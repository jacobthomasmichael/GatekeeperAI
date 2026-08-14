import type { Config } from "tailwindcss";

// ──────────────────────────────────────────────────────────────────────────
// Design tokens — redesign palette (see DESIGN.md / the design-concept
// artifact for rationale). Purely additive: nothing below removes or
// overrides Tailwind's default palette, so existing indigo-*/gray-*/slate-*
// usage across the app is completely unaffected by this change.
//
// Neutral is Tailwind's stock `slate` — a custom warm-toned "graphite"
// neutral was tried first but consistently read as brown at real screen
// scale (see git history), so the app standardizes on slate instead.
// Don't reintroduce a custom neutral token without re-litigating that.
//
// Each remaining family is an 11-step ramp (50–950) generated from one
// hand-picked "anchor" hex, interpolated from near-white through the
// anchor to near-black. The anchor step is noted per family below.
//
// Usage guide:
//   slate-50/900      page background / dark surface       (light / dark)
//   slate-900/white   primary body text                    (light / dark)
//   slate-400/500     secondary/meta text (deliberately lower-contrast —
//                     hints, timestamps)
//   slate-200/700     borders
//   signal-600        primary actions, active nav, focus    (was indigo-600)
//   signal-700        accent text on light backgrounds      (was indigo-700)
//   good/warn/critical  semantic status — kept separate from the signal
//                     accent per design-system convention (was emerald/amber/red)
//
// Accessibility note: warn-700 fails WCAG AA for normal text on a light
// background (3.9:1) — use warn-800 (6.1:1) for warning text on light,
// warn-400 for dark mode. All other families are AA-safe at 700 (light) /
// 400 (dark).
// ──────────────────────────────────────────────────────────────────────────
const tokens = {
  signal: {
    // teal accent — anchor at 600 (#0f6f72)
    50: "#f6fbfc", 100: "#c9eaeb", 200: "#87ecef", 300: "#51e4e8",
    400: "#1dd9de", 500: "#16a4a8", 600: "#0f6f72", 700: "#0d5f62",
    800: "#0b5052", 900: "#0b3d3f", 950: "#092e2f",
  },
  good: {
    // semantic success — anchor at 600 (#2e9e6b)
    50: "#f7fbf9", 100: "#d6eae1", 200: "#a9e6ca", 300: "#84dbb3",
    400: "#5ed09c", 500: "#39c485", 600: "#2e9e6b", 700: "#268158",
    800: "#1d6544", 900: "#184631", 950: "#0e2a1d",
  },
  warn: {
    // semantic warning — anchor at 600 (#d68a2b) — see AA note above
    50: "#fbf9f6", 100: "#efe6da", 200: "#f0d4b1", 300: "#e9c290",
    400: "#e3af6e", 500: "#dc9d4d", 600: "#d68a2b", 700: "#ad6f22",
    800: "#835419", 900: "#563915", 950: "#2d1e0b",
  },
  critical: {
    // semantic danger — anchor at 600 (#d14343)
    50: "#fbf6f6", 100: "#efdddd", 200: "#eebaba", 300: "#e79c9c",
    400: "#df7e7e", 500: "#d86161", 600: "#d14343", 700: "#b22b2b",
    800: "#852121", 900: "#561919", 950: "#2b0d0d",
  },
};

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: tokens,
    },
  },
  plugins: [],
};

export default config;
