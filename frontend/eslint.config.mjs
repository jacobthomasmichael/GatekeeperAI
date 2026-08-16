import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // eslint-config-next's default is "error". The codebase consistently
      // uses the common fetch-on-effect pattern (set loading true, fetch,
      // set loading false + data in .then()) across most data-driven
      // components -- functionally safe, no infinite-loop risk, but flagged
      // by this rule everywhere. Downgraded to a warning so it stays
      // visible (and CI-enforceable going forward) without blocking every
      // PR on a pre-existing, widespread pattern. Fix opportunistically;
      // don't reintroduce it in new code without a reason.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
