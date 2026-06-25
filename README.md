# GatekeeperAI

**Website:** [gatekeeperai.io](https://www.gatekeeperai.io) · **Support:** [jacob@gatekeeperai.io](mailto:jacob@gatekeeperai.io)

GatekeeperAI is an on-premises platform that lets enterprise teams safely adopt third-party and internal AI applications. Every app goes through automated security scanning, human approval, and sandboxed container deployment before any user can access it.

---

## How it works

1. **Submit** — A developer pushes their app's code to the GatekeeperAI git server.
2. **Scan** — The platform automatically runs five scanners: secrets detection, dependency vulnerability audit, egress network analysis, PII exposure check, and an LLM-powered code review via Claude AI.
3. **Review** — A designated approver reviews the scan results and approves or rejects the app, with an SLA deadline tracked automatically.
4. **Deploy** — Approved apps are built into Docker containers and launched in an isolated environment, accessible via a public URL.
5. **Manage** — Runtime secrets (API keys, credentials) are injected as environment variables at deploy time, never stored in the code.

---

## Key features

- **Automated multi-scanner pipeline** — secrets, CVEs, egress rules, PII, and LLM code review run in parallel on every push
- **Risk tiering** — apps are automatically scored and assigned a risk tier (low / medium / high / critical) that determines review urgency
- **SLA enforcement** — overdue approvals are flagged and escalators are notified via email
- **Encrypted secret injection** — per-app secrets are AES-256 encrypted at rest and injected at container startup
- **Per-app access control** — apps are private by default; owners grant access by individual email or by SSO group; nginx `auth_request` enforces this on every request
- **SSO / OIDC** — connect Okta, Azure AD, Google Workspace, Keycloak, or any OIDC-compliant provider; accounts auto-provisioned on first login; IdP groups map to platform roles and per-app access
- **Passkeys** — Touch ID / Face ID / Windows Hello as the default sign-in method; password and SSO sign-in are also supported
- **Audit log** — every action (approval, deployment, secret change) is recorded with actor, IP, and timestamp
- **Admin panel** — user management, SSO configuration, audit log viewer, platform-wide metrics
- **Setup wizard** — first-run wizard configures the instance with no config-file editing required
- **Secure by default** — JWT with refresh token rotation, rate limiting on all endpoints, security headers (CSP, HSTS, etc.), non-root containers
- **OpenTelemetry instrumentation** — distributed tracing across FastAPI, SQLAlchemy, Celery, and Redis; ships to any OTLP-compatible backend (Grafana Tempo, Honeycomb, Datadog, Jaeger) via a single env var

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 |
| Task queue | Celery + Redis |
| Container runtime | Docker SDK (Python) |
| LLM | Anthropic Claude API |
| Frontend | Next.js 16 (App Router) + Tailwind CSS |
| Auth | JWT (access + refresh) + WebAuthn passkeys + OIDC/SSO (authlib) |
| Observability | OpenTelemetry (OTLP export to any compatible backend) |

---

## Getting started

See **[INSTALL.md](./INSTALL.md)** for full setup instructions, including local installation, AWS/Azure/GCP cloud hosting, and custom domain with SSL.

**Quick start (requires Docker):**

```bash
cp .env.example .env
# Fill in SECRET_KEY, SECRET_ENCRYPTION_KEY, and ANTHROPIC_API_KEY in .env
docker compose -f infra/docker-compose.yml pull
docker compose -f infra/docker-compose.yml up -d
```

Pre-built images are pulled from GitHub Container Registry — no compilation required. Then open `http://localhost:3000` and follow the setup wizard.

**To build from source instead:**

```bash
docker compose -f infra/docker-compose.yml up --build
```

---

## Project structure

```
backend/        FastAPI application, scanners, Celery workers, Alembic migrations
frontend/       Next.js web application
infra/          Docker Compose configuration
worker/         Celery task definitions (deploy, SLA checks)
```

---

## User roles

| Role | Can do |
|---|---|
| `ic` (individual contributor) | Submit apps, view own apps and scan results |
| `approver` | Everything an IC can do, plus review and decide on pending approvals, view all deployments |
| `admin` | Everything an approver can do, plus manage users, stop/start deployments, view audit logs |

New users are created by an admin, or provisioned automatically on first SSO login when an OIDC provider is configured. There is no public self-registration.

When SSO is enabled, IdP groups are refreshed on every login and can be mapped to roles in the Admin → SSO tab. Local admin accounts (created during setup with a password) are never demoted by SSO role mappings — they keep their role regardless of what the IdP returns.

---

## Stuck on something?

If you hit a wall during install or setup, please [open an issue](https://github.com/jacobthomasmichael/GatekeeperAI/issues/new?template=bug_report.md) — even a quick one. It helps surface problems that the docs don't cover yet, and most things can be resolved quickly.

For paid support or managed hosting enquiries, email [jacob@gatekeeperai.io](mailto:jacob@gatekeeperai.io).
