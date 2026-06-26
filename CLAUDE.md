# GatekeeperAI — Contributor Context

This file gives AI assistants and human contributors a fast orientation to the codebase: where things live, how the pieces connect, and what to watch out for.

---

## What this repo is

GatekeeperAI is an on-premises platform for governed deployment of AI apps. The full lifecycle:

1. **Submit** — developer uploads a zip or pushes to the built-in git server
2. **Scan** — five automated scanners run concurrently (secrets, CVEs, egress, PII, LLM review)
3. **Review** — an approver reads the scan report and approves or rejects
4. **Deploy** — approved app is built into a container and served behind a reverse proxy; Docker Compose or Kubernetes depending on `DEPLOY_BACKEND`
5. **Access** — users reach the app at a stable URL; GK handles auth, secrets injection, and per-app access control

---

## Repo layout

```
backend/            FastAPI API + Celery workers + scanners
  app/
    config.py       Pydantic settings (reads .env)
    main.py         FastAPI app factory — middleware, routers, lifespan, telemetry init
    telemetry.py    OpenTelemetry setup (FastAPI + SQLAlchemy + Celery + Redis)
    database.py     Async SQLAlchemy engine + session factory
    deps.py         FastAPI dependency injectors (get_db, get_current_user, require_*)
    models/         SQLAlchemy ORM models
    schemas/        Pydantic request/response schemas
    routers/        FastAPI route handlers (one file per domain)
    scanners/       Security scanner implementations + Celery scan task
    services/       Thin service layer called by routers and tasks
                  approval_service.py    — SLA deadline calculation
                  auth_service.py        — password hashing, JWT encode/decode, SSO group→role mapping
                  container_service.py   — Docker SDK wrapper (build, run, stop, health)
                  dockerfile_service.py  — generates hardened Dockerfiles per app type
                  git_service.py         — zip → bare repo, zip flattening
                  k8s_app_service.py     — K8s Deployment/Secret lifecycle (DEPLOY_BACKEND=kubernetes)
                  k8s_build_service.py   — Kaniko build jobs → ECR (DEPLOY_BACKEND=kubernetes)
                  k8s_ingress_service.py — K8s Ingress + ClusterIP Service per app (DEPLOY_BACKEND=kubernetes)
                  log_forwarder.py       — async audit log dispatch (daemon thread, never blocks)
                  nginx_service.py       — writes/removes per-app nginx configs (DEPLOY_BACKEND=docker)
                  notification_service.py — SMTP email for approvers
                  oidc_service.py        — OIDC discovery, PKCE auth flow, token exchange, Redis state
                  secrets_service.py     — Fernet encrypt/decrypt per-app secrets
    middleware/     AuditMiddleware, SecurityHeadersMiddleware
  worker/
    celery_app.py   Celery app definition + Beat schedule
    deploy_task.py  Container build + start Celery task (branches on DEPLOY_BACKEND)
    sla_task.py     Celery Beat task — flags overdue approvals
  alembic/          DB migrations
  tests/            pytest suite (runs against a real test DB)
  scripts/
    seed_review_apps.py   populate the DB with demo apps for local testing

frontend/           Next.js 16 App Router
  AGENTS.md         ⚠ Read this before touching frontend code — documents breaking
                    Next.js API changes that differ from training data
  app/
    login/          Passkey-first login page (also handles SSO redirect + sso_code exchange)
    setup/          First-run wizard
    dashboard/      IC view — submit apps, track status, manage secrets/access/groups
    approvals/      Approver queue + scan report viewer
    deployments/    Admin deployment management
    admin/          User management, audit log, platform metrics, SSO configuration
    account/        Passkey enrollment and management
  components/       Shared components (Sidebar, AuthGuard, ScanResultCard, etc.)
  lib/
    api.ts          All API calls + typed interfaces
    auth.ts         Auth context (user, login, loginWithTokens, logout)

infra/
  docker-compose.yml   Full stack: postgres, redis, api, worker, git-service, frontend, nginx
  nginx/               nginx configs for the main proxy and per-app auth_request gating
  git-service/         Alpine SSH container that receives git pushes
  git-repos/           Bare git repos (created at runtime, not committed)
  authorized_keys      SSH public keys for git push access
  helm/gatekeeperai/   Helm chart for Kubernetes/EKS deployment
  terraform/           EKS cluster, RDS, ElastiCache, ECR, EFS, VPC, IAM/IRSA

GKAPP.md            AI assistant context file for users building GK-compatible apps
INSTALL.md          End-user installation guide (non-technical audience)
```

---

## Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Backend API | FastAPI 0.136 + SQLAlchemy 2.0 async | Python 3.11 |
| Database | PostgreSQL 16 | Port 5433 locally (not 5432 — conflicts with local PG) |
| Task queue | Celery 5.6 + Redis 7.2 | Broker and result backend both Redis |
| Container runtime (Docker) | Docker SDK (Python) | `container_service.py` wraps the SDK |
| Container runtime (K8s) | Kubernetes Python client + Kaniko + ECR | Only loaded when `DEPLOY_BACKEND=kubernetes` |
| LLM | Anthropic Claude API | Used in `llm_scanner.py` for code review |
| Frontend | Next.js 16 (App Router) + Tailwind CSS v3 | webpack, not Turbopack |
| Auth | JWT (access + refresh) + WebAuthn passkeys + OIDC/SSO | 60-min access / 30-day refresh; JTI tracked in Redis; SSO via authlib |
| Observability | OpenTelemetry 1.42 | OTLP HTTP export, no-op when endpoint not set |
| CI | GitHub Actions | Builds + pushes to GHCR on every push to main; also pushes to ECR when `ECR_REGISTRY` secret is set |

---

## Environment variables

All config lives in `.env` (copy from `.env.example`). Key vars:

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing (≥32 chars) |
| `SECRET_ENCRYPTION_KEY` | Yes | AES-256 encryption for per-app secrets (≥32 chars) |
| `ANTHROPIC_API_KEY` | Yes | Powers the LLM scanner |
| `DATABASE_URL` | Set by compose | Overridden in Docker; only needed for local dev outside Docker |
| `REDIS_URL` | Set by compose | Same as above |
| `APP_BASE_URL` | Yes (prod) | Full public URL e.g. `https://gatekeeper.yourcompany.com` |
| `NEXT_PUBLIC_API_URL` | Yes (prod) | Browser-facing API URL |
| `HOOK_SECRET` | Yes (prod) | Authenticates the git post-receive hook to the API |
| `ENVIRONMENT` | Yes | `development` or `production` — gates some security checks |
| `NEXT_PUBLIC_API_URL` | Build-time | **Baked into the Next.js bundle at build time** — changing it requires a frontend rebuild, not just a restart |
| `GIT_SSH_HOST` | Set by compose | Hostname used in dashboard git URLs (default `localhost`) |
| `GIT_SSH_PORT` | Set by compose | SSH port for git push (default `2222`, not 22) |
| `HOOK_CALLBACK_URL` | Set by compose | Internal URL the git post-receive hook calls back to (default `http://api:8000`) |
| `GIT_REPOS_BASE_PATH` | Set by compose | Mount path for bare git repos volume (default `/git-repos`) |
| `DEPLOY_BACKEND` | No | `docker` (default) or `kubernetes` — switches the deploy/stop/restart path |
| `AWS_REGION` | K8s only | AWS region for ECR and S3 build contexts |
| `BUILD_CONTEXT_BUCKET` | K8s only | S3 bucket for Kaniko build contexts (required when `DEPLOY_BACKEND=kubernetes`) |
| `ECR_REGISTRY` | K8s only | ECR registry URL for app images (required when `DEPLOY_BACKEND=kubernetes`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT access token lifetime (default 60) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | JWT refresh token lifetime (default 30) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OTLP HTTP endpoint; omit to discard traces |
| `OTEL_SERVICE_NAME` | No | Defaults to `gatekeeperai` |
| `SMTP_*` | No | Email notifications for approvers |
| `LOG_FORWARD_*` | No | Audit log forwarding (Splunk, Loki, CloudWatch, syslog) |
| `DOCKER_GID` | Linux only | GID of the docker group; needed so the worker can access the Docker socket |
| `RATELIMIT_ENABLED` | Test only | Set to `0` in `tests/conftest.py` to disable rate limiting during tests |

---

## Database models

```
users               id, email, username, role (ic/approver/admin), hashed_password, is_active,
                    sso_subject (nullable, indexed), sso_groups (ARRAY, nullable)
passkeys            id, user_id→users, credential_id, public_key, sign_count, label
app_submissions     id, submitter_id→users, name, description, repo_url, status,
                    risk_tier, detected_type, rejection, allowed_users[], allowed_groups[],
                    visibility
scans               id, submission_id→app_submissions, commit_sha, status, risk_score,
                    risk_tier, findings (JSONB)
approvals           id, scan_id→scans, approver_id→users, decision, comment, decided_at, sla_deadline
deployments         id, submission_id→app_submissions, scan_id→scans, container_id,
                    container_name, image_tag, status, internal_port, external_port,
                    public_url, env_vars_injected, logs_cache,
                    k8s_namespace (nullable), k8s_deployment_name (nullable)
secret_store        id, submission_id→app_submissions, key_name, encrypted_value
sso_configuration   id, provider_name, discovery_url, client_id, encrypted_client_secret,
                    group_claim_key, default_role, role_mappings (JSONB), is_enabled
audit_logs          id, actor_id, action, resource_type, resource_id, ip_address, created_at
```

All migrations live in `backend/alembic/versions/`. To generate a new one:
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Scan pipeline

**Entry points:**
- ZIP upload → `POST /apps/{id}/upload-zip` → `git_service.push_zip_to_repo()` → enqueues `run_scan_pipeline`
- Git push → SSH → `infra/git-service` container → `git_hooks/post-receive` → HTTP call to `/scans/trigger` → enqueues `run_scan_pipeline`

**Pipeline** (`backend/app/scanners/pipeline.py`):
1. Checks out the commit into a temp directory
2. Detects app type (`_detect_app_type`) — reads `requirements.txt` / `package.json` / `index.html`
3. Runs five scanners concurrently via `ThreadPoolExecutor` + `asyncio.gather`; each publishes SSE events as it starts and completes:
   - `secrets_scanner.py` — detect-secrets
   - `dependency_scanner.py` — pip-audit / npm audit
   - `egress_scanner.py` — static analysis for outbound URLs
   - `pii_scanner.py` — regex patterns for PII
   - `llm_scanner.py` — Claude code review via Anthropic API
   - `base.py` — shared `ScanContext` and `ScanResult` dataclasses (not a scanner itself)
4. `risk_engine.py` aggregates findings → risk score (0–100) + tier (low/medium/high/critical)
5. Writes scan record to DB; publishes final `complete` SSE event

Scan events stream to the frontend via `GET /scans/{id}/events` (Server-Sent Events).

---

## Deploy pipeline

**Entry point:** `POST /approvals/{id}/decide` with `decision=approved` → enqueues `deploy_approved_app`

**Task** (`backend/worker/deploy_task.py`) — branches on `DEPLOY_BACKEND`:

**Docker path** (`DEPLOY_BACKEND=docker`, default):
1. Clones the approved commit into a build directory
2. `dockerfile_service.py` generates a hardened Dockerfile (non-root user, `HOME=/tmp`)
3. `container_service.build_image()` — `docker build`
4. `secrets_service.py` decrypts per-app secrets → env vars dict
5. `container_service.start_container()` — `docker run` with: 512 MB RAM, 0.5 CPU, `cap_drop=ALL`, `no-new-privileges`, `read_only=True`, `/tmp` tmpfs
6. `nginx_service.py` writes an nginx config for the app's subdirectory and reloads nginx
7. Health check polls the container; updates deployment status in DB

**Kubernetes path** (`DEPLOY_BACKEND=kubernetes`):
1. Clones the approved commit into a build directory
2. `dockerfile_service.py` generates a hardened Dockerfile
3. `k8s_build_service.build_and_push()` — tars build context → S3 → Kaniko Job → ECR image URI
4. `secrets_service.py` decrypts per-app secrets → env vars dict
5. `k8s_app_service.deploy_app()` — creates K8s Secret + Deployment in `gatekeeperai-apps` namespace
6. `k8s_ingress_service.write_app_ingress()` — creates ClusterIP Service + Ingress with auth-url annotation
7. Polls pod readiness; updates deployment status in DB with `k8s_namespace` and `k8s_deployment_name`

**App URL pattern:** `https://your-domain.com/apps/{safe-name}/`

**App type → Dockerfile mapping** (`dockerfile_service.py`):

| Detected type | Entry point | Port |
|---|---|---|
| `python-streamlit` | `app.py` | 8501 |
| `python-gradio` | `app.py` | 7860 |
| `python-web` (Flask/FastAPI) | `app.py` | 8000 |
| `python` (generic) | `main.py` | 8000 |
| `nodejs` / `nodejs-next` | `index.js` | 3000 |
| `static` | `index.html` | served by nginx directly |

Detection reads `requirements.txt` for Python apps and `package.json` for Node. Zip uploads are automatically flattened if the user zipped a folder (strips single-subdirectory nesting and `__MACOSX/`).

All generated Dockerfiles (except `static`) create a non-root system user, `chown /app`, set `ENV HOME=/tmp`, and switch to that user before the entrypoint.

---

## Auth model

- **Login:** email + password OR passkey (WebAuthn) OR SSO/OIDC. Passkey is the default UI flow.
- **SSO/OIDC:** configured by an admin in the Admin → SSO tab. Stored in `sso_configuration` table (one row max). On first SSO login, accounts are auto-provisioned; IdP groups are refreshed on every login and mapped to platform roles via `role_mappings`. Local admin accounts (with `hashed_password` set) are never demoted by SSO role mappings.
- **Tokens:** access JWT (60 min, `ACCESS_TOKEN_EXPIRE_MINUTES`) + refresh JWT (30 days, `REFRESH_TOKEN_EXPIRE_DAYS`). Refresh tokens are tracked by JTI in Redis; logout invalidates the JTI.
- **Passkeys:** stored in `passkeys` table. `@simplewebauthn/server` on the backend, `@simplewebauthn/browser` on the frontend (dynamic import).
- **Per-request auth:** `deps.py` → `get_current_user` decodes the access JWT from the `Authorization: Bearer` header.
- **nginx auth_request:** every request to a deployed app hits `GET /api/v1/auth/verify?app={safe_name}` before being proxied. The verify endpoint checks JWT + per-app `allowed_users` allowlist + per-app `allowed_groups` (SSO groups).

---

## Per-app access control

Apps default to owner-only access. Access is granted via individual user IDs (`allowed_users`) or SSO group names (`allowed_groups`). Rules:

| Actor | Access |
|---|---|
| Submitter (owner) | Always |
| Users in `allowed_users` | Granted |
| Users whose SSO groups intersect `allowed_groups` | Granted |
| Approver / Admin | Always (operational bypass) |
| All other ICs | Blocked (403 from nginx auth_request) |
| Public apps | No auth at all |

---

## Frontend routing

All pages are under `frontend/app/` using Next.js App Router.

| Route | Who sees it | Purpose |
|---|---|---|
| `/login` | Everyone | Passkey, password, or SSO login; handles `?sso_code=` exchange |
| `/setup` | Admin (first run) | Setup wizard |
| `/dashboard` | IC | Submit apps, track status, manage secrets/access/groups |
| `/dashboard/submit` | IC | Submit a new app |
| `/dashboard/scans/[id]` | IC | Live scan report |
| `/approvals` | Approver | Review queue |
| `/deployments` | Admin | Manage running containers |
| `/admin` | Admin | Users, audit log, metrics, SSO configuration |
| `/account` | Any logged-in user | Passkey enrollment |

`AuthGuard` (`components/AuthGuard.tsx`) wraps protected routes and redirects to `/login?next=...` if no valid token. Role enforcement (redirecting an IC away from `/admin`) is also in AuthGuard.

`lib/api.ts` is the single source of truth for all API calls and TypeScript types. Add new endpoints here first.

---

## Running locally (outside Docker)

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Postgres must be running on port 5433; Redis on 6379
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A worker.celery_app.celery_app worker --loglevel=info   # separate terminal
celery -A worker.celery_app.celery_app beat --loglevel=info     # separate terminal (SLA checks)
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

**Full stack (recommended):**
```bash
cp .env.example .env   # fill in SECRET_KEY, SECRET_ENCRYPTION_KEY, ANTHROPIC_API_KEY
docker compose -f infra/docker-compose.yml up --build
```

> **nginx runs in the `production` profile only.** In the default compose setup nginx is not started — the frontend and API are accessed directly on ports 3000 and 8000. To include nginx: `docker compose -f infra/docker-compose.yml --profile production up`.

> **Git SSH runs on port 2222.** The `git` service exposes SSH on port 2222 (not 22) to avoid requiring root. Add your public key to `infra/authorized_keys` and clone with `git clone ssh://git@localhost:2222/git-repos/<app-name>.git`.

---

## Tests

```bash
cd backend
# Requires a running Postgres at localhost:5433 with a 'gatekeeperai_test' database
pytest                        # all tests
pytest tests/test_auth.py     # single file
pytest -k "passkey"           # filter by name
```

Tests run against a **real test database** (`gatekeeperai_test`), not mocks. The conftest creates and drops tables on each run. Rate limiting is disabled in tests via `RATELIMIT_ENABLED=0`.

Test files:

| File | Covers |
|---|---|
| `test_auth.py` | Login, token refresh, logout, JWT validation |
| `test_passkeys.py` | WebAuthn registration and authentication flows |
| `test_apps.py` | App submission, zip upload, status transitions |
| `test_approvals.py` | Approval, rejection, SLA deadline |
| `test_rbac.py` | Role enforcement on every endpoint |
| `test_secrets.py` | Secret create/read/delete, encryption |
| `test_risk_engine.py` | Risk scoring logic |
| `test_hardening.py` | Rate limiting, security headers, CSP |
| `test_blue_green.py` | Deploy/stop/restart transitions |
| `test_admin.py` | User management endpoints |
| `test_setup.py` | First-run wizard flow |
| `test_telemetry.py` | OpenTelemetry provider, span recording, FastAPI instrumentation |
| `test_k8s_services.py` | K8s build, app, and ingress service unit tests (mocked K8s client) |

---

## CI / CD

`.github/workflows/publish.yml` — triggers on every push to `main`:
1. Builds three Docker images: `gatekeeperai-backend`, `gatekeeperai-frontend`, `gatekeeperai-git-service`
2. Pushes all three to GHCR (`ghcr.io/jacobthomasmichael/...`) with `latest` tag
3. Also pushes to ECR if the `ECR_REGISTRY` secret is set in the repo
4. Multi-platform: `linux/amd64` + `linux/arm64`

To deploy a new version on a running EC2 instance:
```bash
cd /opt/gatekeeperai
sudo docker compose -f infra/docker-compose.yml pull
sudo docker compose -f infra/docker-compose.yml up -d
```

---

## Common gotchas

- **Three separate Celery processes.** The compose stack runs `api`, `worker`, and `beat` as separate containers. Locally you need three terminals: uvicorn, `celery worker`, and `celery beat`. Missing `beat` means SLA checks never run.
- **nginx is production-profile-only.** `docker compose up` (no profile) skips nginx entirely. Add `--profile production` to include it.
- **Tailwind v4 / Turbopack are not used.** arm64 binary signing issues blocked both. Stick with Tailwind v3 and webpack.
- **Postgres runs on 5433 locally**, not 5432, to avoid conflicts with a local Postgres installation.
- **Docker socket access on Linux** — the worker container needs `DOCKER_GID` set to the host docker group GID so it can call the Docker API.
- **npm lockfile format** — the Docker build uses `node:20-alpine` (npm v10). If you regenerate `package-lock.json` locally with npm v11, the build will fail. Regenerate inside the container: `docker run --rm -v $(pwd)/frontend:/app -w /app node:20-alpine npm install`
- **OTel provider is set once at import time** — `main.py` calls `setup_telemetry(app)` at module level. Tests that need span recording should use `provider.get_tracer()` directly rather than the global `trace.get_tracer()`.
- **Mac zip uploads** — GK automatically flattens single-subdirectory zips and strips `__MACOSX/`. Users can zip either a folder or its contents.
- **Streamlit API versions** — `st.context.headers` and `use_container_width` require `streamlit>=1.37`. Recommend `streamlit==1.40.0` in `GKAPP.md` examples.
- **Deployed containers have a read-only root filesystem.** Only `/tmp` is writable (128 MB tmpfs). Apps that write outside `/tmp` at runtime will crash. `HOME=/tmp` is set in all generated Dockerfiles to redirect common write paths (pip cache, framework temp files) there.
- **K8s mode requires three env vars** — `DEPLOY_BACKEND=kubernetes` will fail at startup unless `BUILD_CONTEXT_BUCKET` and `ECR_REGISTRY` are also set. The Pydantic validator raises a clear error if they're missing.
- **K8s resource name length** — `safe_name` (from the app name) is truncated before being used in K8s resource names to stay within the 63-char limit. The app name validator caps names at 50 chars.
- **SSO admin lockout guard** — if a user account has a `hashed_password` set (i.e. created locally, not via SSO), the SSO callback never updates their role. This prevents the setup admin from being demoted if they also happen to exist in the IdP.
