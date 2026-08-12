# Snake — GatekeeperAI worked example

A minimal single-file Python app (stdlib `http.server`, no dependencies) used as the concrete example in [`DESIGN.md`](../../DESIGN.md)'s architecture diagrams. It's a playable Snake game with a SQLite-backed leaderboard.

This example is included **as originally submitted, warts and all** — it's more useful as a teaching example that way than a sanitized happy path. Two things about it are worth knowing before you deploy it:

## It has no `requirements.txt`, `package.json`, or `index.html`

That means GatekeeperAI's type detector (`_detect_app_type` in `backend/app/scanners/pipeline.py`) returns `None` for this submission — it isn't classified as `python`, `python-web`, or anything else.

That's fine here because **this submission includes its own `Dockerfile`**, and GatekeeperAI only generates one when the repo doesn't already have one (`backend/worker/deploy_task.py`). The platform parses `EXPOSE 8000` out of the submitted Dockerfile to determine the container's internal port — it doesn't need `detected_type` to be set for that to work.

One consequence: this Dockerfile has no `USER` directive, so the process runs as root *inside* the container namespace — unlike GatekeeperAI's own generated Dockerfiles, which always create and switch to a non-root user. The platform's runtime hardening (read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, resource limits) still applies regardless of what's in the image, since those are enforced at `docker run` / pod `securityContext` time — but the non-root guarantee specifically comes from the Dockerfile, and a submitter who brings their own Dockerfile is opting out of it.

## It writes to `/data/scores.db` by default

`main.py` defaults `DB_PATH` to `/data/scores.db`. GatekeeperAI's deployed containers run with a **read-only root filesystem** — only `/tmp` is writable (128 MB tmpfs). As submitted, this app will crash on startup (`os.makedirs("/data", ...)` fails with `PermissionError`) unless you configure a secret before deploying:

```
DB_PATH=/tmp/scores.db
```

This isn't a bug in the example — it's left in deliberately, because it's a real, concrete illustration of what "read-only root filesystem" actually means for a submitted app, rather than just a bullet point in the README.

## Running it locally (outside GatekeeperAI)

```bash
cd examples/snake-app
DB_PATH=./scores.db python3 main.py
# → http://localhost:8000
```
