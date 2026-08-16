# Contributing to GatekeeperAI

Thank you for your interest in contributing! Here's how to get involved.

---

## Start here

**[CLAUDE.md](./CLAUDE.md)** is the primary reference for working in this codebase — repo layout, tech stack, database models, the scan and deploy pipelines, auth model, environment variables, and a running list of gotchas (port numbers, Tailwind version, npm lockfile quirks, etc.). Read it before your first PR; it'll save you from re-discovering things that are already documented.

**[INSTALL.md](./INSTALL.md)** covers getting the full stack running locally via Docker Compose. **[DESIGN.md](./DESIGN.md)** explains the reasoning behind major architecture decisions, if you're curious why something was built the way it was.

---

## Ways to contribute

- **Bug reports** — open a GitHub issue with steps to reproduce
- **Feature requests** — open a GitHub issue describing the problem you're trying to solve
- **Pull requests** — bug fixes, improvements, and new features are welcome
- **Documentation** — improvements to the README, INSTALL.md, or inline docs

---

## Getting started

1. Fork the repository and clone your fork
2. Follow the setup instructions in [INSTALL.md](./INSTALL.md) to get the stack running locally
3. Create a branch for your change: `git checkout -b your-feature-name`
4. Make your changes and test them
5. Open a pull request against the `main` branch

---

## Branching

Work happens on a feature branch, never directly on `main`. Name it after what it does — `fix/`, `feat/`, `docs/` prefixes are common in this repo's history but not required. One focused change per branch/PR.

---

## Commit messages

This repo loosely follows [Conventional Commits](https://www.conventionalcommits.org/). Prefix your commit subject with one of:

| Prefix | Use for |
|---|---|
| `feat:` | A new feature |
| `fix:` | A bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests, no production code change |
| `refactor:` | Code change that's neither a fix nor a feature |
| `perf:` | A performance improvement |
| `chore:` | Everything else (deps, CI config, tooling) |

Not strictly enforced, but keeps `git log` and the release notes readable — this project generates its changelogs directly from commit history.

---

## CI — what actually runs on your PR

Every push and every PR into `main` triggers [`.github/workflows/test.yml`](./.github/workflows/test.yml), which runs two independent jobs:

**`backend`** — the full pytest suite against a real Postgres + Redis (spun up as CI service containers, not mocked). To run the same thing locally:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Postgres must be running on port 5433 with a `gatekeeperai_test` database
RATELIMIT_ENABLED=0 pytest
```

**`frontend`** — lint, a TypeScript type-check, and a production build. To run the same thing locally:

```bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

A few `react-hooks/set-state-in-effect` warnings are expected and won't fail CI — see the comment in `eslint.config.mjs` for why. Everything else should be clean; a red X on either job means something needs fixing before merge.

---

## Pull request guidelines

- Keep PRs focused — one change per PR makes review faster
- Include a clear description of what the change does and why
- If fixing a bug, describe how to reproduce it
- If adding a feature, explain the use case it addresses
- New backend logic should come with test coverage; frontend changes should pass `tsc` and `build` locally before you push (CI will catch it either way, but it's faster to know upfront)

---

## Reporting security vulnerabilities

Please do **not** open a public issue for security vulnerabilities. See [SECURITY.md](./SECURITY.md) for the responsible disclosure process.

---

## Code style

- **Backend (Python):** follow PEP 8, use type hints
- **Frontend (TypeScript):** follow the existing patterns in the codebase; `npm run lint` will catch most style issues

---

## Questions?

Open a GitHub issue and tag it with the `question` label.
