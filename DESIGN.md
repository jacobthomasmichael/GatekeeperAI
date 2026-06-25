# Design Decisions

A summary of the key choices behind GatekeeperAI's architecture — what I picked, what I traded away, and where the design starts to crack under pressure.

---

## Why this stack

**FastAPI over Django or Flask**
The core constraint was a streaming scan pipeline. Scans run five checks in parallel and stream results to the browser via Server-Sent Events as each check completes. FastAPI's async-first model handles this naturally — Django's ORM and request lifecycle fight it. Flask could work but you end up bolting on async support that wasn't designed in. FastAPI also generates OpenAPI docs automatically, which matters when you're building a platform that other developers integrate with.

**SQLAlchemy 2.0 async + PostgreSQL**
I needed two things the alternatives don't give cleanly: JSONB columns for scan findings (structured but schema-flexible across scanner types) and UUID arrays for per-app access control (`allowed_users UUID[]`). PostgreSQL handles both natively. SQLAlchemy 2.0's async session model pairs well with FastAPI — one `AsyncSession` per request, injected as a dependency, closed automatically. The tradeoff is verbosity: async SQLAlchemy is more ceremonial than a lightweight ORM like Tortoise, but the explicitness is worth it when you're dealing with concurrent scan and deploy tasks touching the same rows.

**Celery + Redis for task execution**
Scans take 15–60 seconds. Deploys involve a `docker build`, which can take several minutes. Neither belongs in the request/response cycle. Celery gives task isolation, retry logic, and a clean boundary between the API and the work — the API enqueues, the worker executes, the result lands in the database. Redis was already required for JWT refresh token JTI tracking, so using it as the Celery broker and result backend costs nothing architecturally. The three-process model (API, worker, beat) adds local dev friction but is the right separation — beat handles SLA checks on a cron without touching the worker's task queue.

**Docker SDK (Python) over shell exec**
`subprocess.run(["docker", "build", ...])` is the obvious first move, but it couples you to the Docker CLI binary, makes error handling messy, and is a pain to test. The Python Docker SDK gives a proper object model — containers, images, logs — and makes it straightforward to check `container.status`, stream logs, and catch `NotFound` exceptions when a container disappears between calls.

**nginx auth_request for per-app access control**
Every request to a deployed app passes through nginx before it reaches the container. Rather than requiring each app to implement its own auth (which apps built by non-engineers won't do correctly), nginx's `auth_request` directive calls a GatekeeperAI endpoint before proxying. If the response is 2xx the request goes through; otherwise nginx returns 401 or 403. The deployed app never sees unauthenticated traffic. The tradeoff is that every request to a deployed app makes a subrequest to the GatekeeperAI API — a performance cost that's acceptable at small scale but would need caching at high load.

**Passkeys as the default sign-in method**
Passkeys are phishing-proof by construction (the credential is bound to the origin), and Touch ID / Face ID are faster than any password flow. The WebAuthn spec is mature enough that `@simplewebauthn/server` and `@simplewebauthn/browser` cover the complexity. Password auth stays available as a fallback for devices that don't support platform authenticators. I'd rather default to the secure path and fall back than default to passwords and offer passkeys as an opt-in that nobody enables.

**SSO / OIDC as the enterprise on-ramp**
Passkeys are the right default for individuals, but enterprise procurement requires SSO — "we already manage identities in Okta, we're not maintaining a second directory." The implementation uses `authlib` for the OIDC Authorization Code Flow with PKCE. Discovery document caching in Redis (1-hour TTL, invalidated on config update) avoids a round-trip on every login without letting stale metadata sit forever.

The callback-to-frontend token handoff is the least obvious part: the OIDC callback is a browser redirect (GET), so you can't return JSON tokens directly. The solution is a short-lived exchange code stored in Redis (UUID key, 120-second TTL, consumed via GETDEL). The IdP redirects the browser to `/login?sso_code={uuid}`, the frontend POSTs that code to `/auth/sso/exchange`, and the exchange returns normal access + refresh tokens. Single-use and time-limited — if the browser never completes the exchange, the code expires harmlessly.

Group-to-role mapping uses a priority dict (`admin:3 > approver:2 > ic:1`) so users who belong to multiple groups always get their highest entitled role. Groups are written back to `users.sso_groups` on every login, which means the nginx `auth_request` endpoint for per-app group access always reflects current IdP state without an extra IdP call at request time.

One deliberate constraint: local admin accounts (those with a `hashed_password`) are never demoted by SSO role mappings. An IdP misconfiguration that returns no groups or the wrong groups for the setup admin cannot lock the operator out of their own instance.

---

## The LLM scanner — where it helps and where it doesn't

The fifth scanner sends the submitted code to Claude for a code review focused on security and AI-specific risks (prompt injection, model output handling, PII exposure patterns, unusual outbound connections). It's the only scanner that can reason about *intent* rather than just matching patterns.

**Where it's useful:** Catching things the static scanners can't — a function that looks structurally fine but is clearly logging user inputs to an external API, or a Streamlit app that renders LLM output as raw HTML. These require understanding context, not regex.

**Where it isn't reliable:** It's non-deterministic, it can miss things, and it can hallucinate findings. A low-severity finding from the LLM scanner shouldn't block an approval the same way a hardcoded AWS key should. More importantly, the app code itself is attacker-controlled — a malicious submission could include prompt injection attempts in comments or strings. The LLM review is one signal among five, not the decision-maker. The human approval step exists precisely because no combination of automated checks constitutes a security guarantee.

So the scanner raises the floor and surfaces obvious issues automatically. It doesn't replace a security engineer reading the code. (Job security!)

**Current dependency:** The scanner is tightly coupled to the Anthropic API today — `llm_scanner.py` makes direct `anthropic.Anthropic()` calls. For enterprises that have negotiated a BAA with a different provider (Azure OpenAI is common in healthcare and finance, Vertex AI in Google-shop orgs), swapping backends isn't currently possible without forking the scanner. A thin `LLMReviewer` interface with provider-specific implementations would decouple this cleanly — the scan result schema doesn't care which model produced it. That's a natural next step once the core workflow is proven out.

---

## Tradeoffs I made knowingly

**Single-host Docker model**
Every deployed app runs as a container on the same host as the GatekeeperAI stack. This is the right call for the target deployment (a single EC2 instance or on-prem server), and it keeps the install story simple — one `docker compose up` and everything works. The cost is that there's no isolation between a misbehaving app and the platform itself, and you're constrained to one machine's resources.

**nginx config file writes from the Celery worker**
When an app is deployed, the worker writes a `.conf` file to disk and reloads nginx. It works, but it's a design smell: writing files from an application process to configure a system service is the kind of thing that breaks in subtle ways (permissions, race conditions on concurrent deploys, config syntax errors that take down all apps). At meaningful scale this should be replaced with a proper ingress controller that accepts dynamic configuration via API.

**No container registry**
Built images are stored on the local Docker host. At small scale this is fine. At larger scale you'd want images pushed to a registry (ECR, GHCR) so multiple hosts can pull them, and so the local disk doesn't fill up. The current design has no image pruning — something to add.

**Git-based submission as a first-class path**
The platform supports both zip upload and git push. Git push goes through a separate SSH container that runs the post-receive hook, which adds operational surface area (another container, SSH key management, hook authentication). For most internal teams, zip upload is simpler and sufficient. The git path exists because it's the right long-term model — version history, incremental pushes, CI integration — but it adds complexity that a simpler v1 might have deferred.

---

## What breaks first at 100x scale

**The single Docker host.** One hundred deployed apps mean one hundred running containers on one machine. The resource limits (512 MB RAM, 0.5 CPU per container) provide some protection, but a single host isn't the right model here. Docker was the right call for a fast first pass — the primitives (build, run, stop, logs) map directly to the platform's operations and kept the v1 install story to a single `docker compose up`. The target architecture is EKS or a self-hosted Kubernetes cluster, where each deployed app becomes a pod with proper resource quotas, horizontal scaling, and network policies. The container-per-app model translates cleanly — it's the orchestration layer underneath that needs to change, not the deployment model itself.

**The auth_request subrequest on every proxied request.** At 100x traffic, every request to every deployed app hits the GatekeeperAI API for an auth check. The verify endpoint is fast (JWT decode + one DB query), but it becomes a bottleneck and a single point of failure. The fix is caching at the nginx layer — a short TTL cache keyed on the token + app name would eliminate most of the subrequests.

**The LLM scanner cost.** At 100x submissions, Claude API costs become significant — especially for large codebases. Rate limiting per submission and cost controls per team would be necessary. An async queue with backpressure would prevent a burst of submissions from generating a large unexpected bill.

**Local image storage.** Docker images build up on disk with no pruning. A container registry and a cleanup policy are necessary before this runs unsupervised.

**Single Celery worker.** The current setup runs one worker process handling both scan tasks (fast, CPU-bound) and deploy tasks (slow, I/O-bound). Dedicated queues per task type with separate worker pools would prevent a batch of large deploys from starving the scan queue.

---

## What I'd do differently starting over

**The nginx config file approach.** I'd evaluate Traefik or Caddy from the start — both support dynamic configuration via API and would eliminate the file-write pattern. The current approach works but it's the part of the codebase I'd be most cautious about modifying.

**App type detection.** The current heuristic reads `requirements.txt` and `package.json` to classify apps (Streamlit, Gradio, Flask, Node, static). It's surprisingly effective but breaks on non-standard layouts. A more robust approach would scan all files for entry point patterns rather than relying on one or two indicator files.

**The scan result schema.** Findings are stored as JSONB — flexible but untyped. As the scanner count grows and findings become more structured, a proper findings table with a discriminated type column would make querying and aggregating results much cleaner.
