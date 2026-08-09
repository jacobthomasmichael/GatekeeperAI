# GatekeeperAI

**Website:** [gatekeeperai.io](https://www.gatekeeperai.io) · **Support:** [jacob@gatekeeperai.io](mailto:jacob@gatekeeperai.io)

> **Status: v0.2 — active development.** The full lifecycle (scan → approve → deploy → access control) is implemented and working. The platform is suitable for internal pilots and teams that want to evaluate the approach. If you find gaps or rough edges, [open an issue](https://github.com/jacobthomasmichael/GatekeeperAI/issues/new) — that feedback directly shapes what gets hardened next.

GatekeeperAI is an on-premises platform that lets teams safely adopt third-party and internal AI applications. Every app goes through automated security scanning, human approval, and sandboxed container deployment before any user can access it.

---

## How it works

1. **Submit** — A developer pushes their app's code to the GatekeeperAI git server.
2. **Scan** — The platform automatically runs five scanners: secrets detection, dependency vulnerability audit, egress network analysis, PII exposure check, and an LLM-powered code review via Claude AI.
3. **Review** — A designated approver reviews the scan results and approves or rejects the app, with an SLA deadline tracked automatically.
4. **Deploy** — Approved apps are built into Docker containers and launched in an isolated environment, accessible via a public URL.
5. **Manage** — Runtime secrets (API keys, credentials) are injected as environment variables at deploy time, never stored in the code.

---

## Key features

- **Automated multi-scanner pipeline** — secrets detection, CVE audit, egress analysis, PII check, and LLM code review run concurrently on every push
- **Risk tiering** — apps are automatically scored and assigned a risk tier (green / yellow / red, with any scanner able to force red) that determines review urgency
- **SLA enforcement** — overdue approvals are flagged and escalators are notified via email
- **Encrypted secret injection** — per-app secrets are AES-256 encrypted at rest and injected at container startup
- **Per-app access control** — apps are private by default; owners grant access by individual email or by SSO group; nginx `auth_request` enforces this on every request
- **SSO / OIDC** — connect Okta, Azure AD, Google Workspace, Keycloak, or any OIDC-compliant provider; accounts auto-provisioned on first login; IdP groups map to platform roles and per-app access
- **Passkeys** — Touch ID / Face ID / Windows Hello as the default sign-in method; password and SSO sign-in are also supported
- **Audit log** — every action (approval, deployment, secret change) is recorded with actor, IP, and timestamp
- **Admin panel** — user management, SSO configuration, audit log viewer, platform-wide metrics
- **Setup wizard** — first-run wizard configures the instance with no config-file editing required
- **Container security controls** — deployed apps run as non-root, with all Linux capabilities dropped, `no-new-privileges` enforced, and a read-only root filesystem (writable `/tmp` via tmpfs); CPU and memory limits applied at runtime
- **Platform security** — JWT with refresh token rotation, rate limiting on all endpoints, security headers (CSP, HSTS, X-Frame-Options), AES-256 encrypted secrets at rest
- **Dual deployment targets** — Docker Compose for single-host on-premises installs; Kubernetes/EKS with Helm and Terraform for larger deployments (HPA, KEDA autoscaling, NetworkPolicy, PodDisruptionBudgets)
- **OpenTelemetry instrumentation** — distributed tracing across FastAPI, SQLAlchemy, Celery, and Redis; ships to any OTLP-compatible backend (Grafana Tempo, Honeycomb, Datadog, Jaeger) via a single env var

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 |
| Task queue | Celery + Redis |
| Container runtime | Docker SDK (Python) · Kubernetes (EKS) + Helm + Terraform |
| Deployment | Docker Compose (single-host) · Kubernetes/EKS (Helm chart + Terraform) |
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

**For Kubernetes/EKS deployment**, see the [EKS setup guide](./INSTALL.md) in INSTALL.md — it covers Terraform provisioning, ECR image push, and Helm chart installation.

---

## Project structure

```
backend/            FastAPI application, scanners, Celery workers, Alembic migrations
frontend/           Next.js web application
infra/              Docker Compose, nginx configs, and Kubernetes infrastructure
  docker-compose.yml
  helm/gatekeeperai/ Helm chart for EKS deployment (api, worker, beat, frontend, git-service)
  terraform/         EKS cluster, RDS, ElastiCache, ECR, EFS, VPC, IAM/IRSA
worker/             Celery task definitions (deploy, SLA checks)
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

## Security model

GatekeeperAI deploys arbitrary submitted code — that is its purpose — so the security model is worth being explicit about.

**What is enforced today:**
- Deployed containers run as a non-root system user (`appuser` / `node`)
- All Linux capabilities dropped; `no-new-privileges` set; read-only root filesystem
- CPU (0.5 cores) and memory (512 MB) hard limits per app
- Per-app `auth_request` gating via nginx — unauthenticated requests never reach the app process
- Platform API: JWT auth, rate limiting, CSP/HSTS headers, AES-256 encrypted secrets at rest
- Kubernetes mode adds: NetworkPolicy blocking RFC-1918 egress, ResourceQuota on the app namespace, non-root + drop-ALL securityContext on all platform pods

**What is not enforced today (known gaps):**
- No syscall filtering (seccomp) or mandatory access control (AppArmor) on deployed containers
- No egress deny-by-default for Docker mode — apps can reach the internet; the egress scanner flags URLs but does not block them at runtime
- No post-build image scanning or SBOM generation
- No signed build provenance (Sigstore/cosign)
- The generated Dockerfiles install submitted `requirements.txt` / `package.json` without a pinned lockfile — supply-chain risk sits with the submitter

These are tracked as known gaps for future hardening. The platform is appropriate for internal tooling and pilots where submitters are trusted employees; it is not a substitute for a full container security platform (Falco, OPA Gatekeeper, etc.) in a zero-trust environment.

---

## Stuck on something?

If you hit a wall during install or setup, please [open an issue](https://github.com/jacobthomasmichael/GatekeeperAI/issues/new?template=bug_report.md) — even a quick one. It helps surface problems that the docs don't cover yet, and most things can be resolved quickly.

For paid support or managed hosting enquiries, email [jacob@gatekeeperai.io](mailto:jacob@gatekeeperai.io).
