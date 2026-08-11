# GKAPP.md — GatekeeperAI App Builder Context

> **How to use this file:** Paste the contents into your AI assistant (Claude, ChatGPT, Gemini, Grok, Copilot, etc.) as a system prompt or at the start of your conversation before describing what you want to build. The assistant will use this context to generate an app that works correctly inside GatekeeperAI without building things GK already handles for you.

---

## What is GatekeeperAI?

GatekeeperAI is a governed deployment platform for internal AI apps. When someone submits an app, GatekeeperAI handles:

- **Authentication** — every request hitting your app has already been verified by GatekeeperAI. You do not need to build login pages, sessions, JWTs, or user tables.
- **Deployment** — your app runs in a Docker container. GatekeeperAI generates the Dockerfile automatically. You do not need to write one.
- **Networking** — your app is served at a stable URL behind a reverse proxy. You do not need to configure ports, TLS, or nginx.
- **Access control** — the app owner controls who can access the app. You do not need to build permission systems.
- **Secret management** — sensitive values (API keys, database URLs, etc.) are configured by the app owner in GatekeeperAI's secrets manager and injected as environment variables at runtime.

**Your job is to build the application logic. GatekeeperAI handles everything around it.**

---
## Conversational Build Starter

When helping a user build a GatekeeperAI app, start by asking these questions one at a time before writing any code:

```
1. What problem are you trying to solve? Describe it in plain language.

2. Who will use this app — just you, a specific team, or your whole organization?

3. What does the app need to do? Walk me through a typical session:
   - What does the user see first?
   - What do they input or interact with?
   - What does the app do with that?
   - What does the user get back?

4. Does the app need to remember data between sessions (e.g. save results, track history)?
   If yes: describe what needs to be saved.

5. Does the app need to connect to anything external?
   Examples: a database, an API, a spreadsheet, an email service, Slack.
   If yes: what credentials or connection details would be needed?

6. Does the app use an AI model (e.g. summarization, chat, classification)?
   If yes: which provider, or should we use whatever API key the user has?

Once you have answers to these questions, propose a brief plan (what the app will do, what it will look like, what libraries you'll use) and confirm before writing code.
```

---

## What NOT to Build

Do not generate any of the following — GatekeeperAI already provides them:

| Skip this | GK handles it |
|-----------|--------------|
| Login / signup pages | Auth is handled at the proxy layer |
| Session management | Every request is pre-authenticated |
| User database / user table | Users are managed by GatekeeperAI |
| JWT or token generation | GK issues and validates all tokens |
| Dockerfile | Auto-generated from your app type |
| nginx / web server config | Handled by GK's reverse proxy |
| Port configuration | GK assigns and maps ports automatically |
| SSL/TLS setup | Terminated by GK before reaching your app |
| Role/permission middleware | Access control is managed in GK |

---
## Alternate Conversation Starter

```
We're going to plan and build [PROJECT] together. Here's how I want to work:

1. Plan backward from the end state. I'll describe the destination first. Before writing any code, restate your understanding of the end state back to me, then propose a chunked sequence of steps working backward from it to where we are now. Flag any assumption or ambiguity before proceeding — don't guess silently.

2. Each chunk needs a visible checkpoint. Every chunk should end in something demoable — a working endpoint, a passing test, visible output — not just code that compiles. If a chunk can't produce something demoable on its own, tell me and we'll re-split it.

3. Log real decisions as we go, not at the end. Any time we hit a genuine fork — a library choice, an architecture call, a tradeoff — before proceeding, state the choice, the alternative(s) considered, and the reasoning in 2-4 sentences, and add it to a running DECISIONS.md. Skip logging for boilerplate or obvious choices; only log the ones where someone could reasonably ask "why not the other way?"

4. Interrupt me if I miss something. If I move forward too fast and skip a real risk, edge case, or requirement gap, stop and flag it before continuing — even if I didn't ask.

5. Prefer existing, well-established patterns/libraries over building from scratch, unless there's a specific reason not to — and if you recommend one, name it explicitly and briefly say why it fits.

Here's the end state: [describe destination]
```

## Accessing the Current User

GatekeeperAI injects the authenticated user's information into every request via HTTP headers. Read these in your app to personalize behavior:

```python
# Available on every request — no auth code needed
user_email = request.headers.get("X-GK-User-Email")   # e.g. "sarah@company.com"
user_id    = request.headers.get("X-GK-User-Id")      # UUID string
user_role  = request.headers.get("X-GK-User-Role")    # "ic", "approver", or "admin"
```

**Streamlit example:**
```python
import streamlit as st

# st.context.headers available in Streamlit >= 1.37
st.write(f"Welcome, {st.context.headers.get('X-GK-User-Email', 'teammate')}")
```

---

## Using Secrets

Sensitive values are configured by the app owner in GatekeeperAI's Secrets Manager — never hardcode them. At runtime they are available as standard environment variables:

```python
import os

# These are set by GatekeeperAI at deploy time — never hardcode
openai_key  = os.environ["OPENAI_API_KEY"]
db_url      = os.environ["DATABASE_URL"]
slack_token = os.environ["SLACK_BOT_TOKEN"]
```

Tell the user what secret names their app expects. They will add them in GatekeeperAI before deploying.

---

## Supported App Types

GatekeeperAI auto-detects your app type and generates the appropriate Dockerfile:

| Type | Entry point | Detection |
|------|-------------|-----------|
| **Python / Flask** | `app.py` with `app = Flask(__name__)` | `requirements.txt` present |
| **Python / FastAPI** | `main.py` with `app = FastAPI()` | `requirements.txt` + fastapi |
| **Python / Streamlit** | `app.py` with `st.` calls | `streamlit` in requirements |
| **Node.js** | `index.js` or `server.js` | `package.json` present |
| **Static** | `index.html` | No server framework detected |

**Recommended for non-technical builders: Streamlit.** It produces interactive web apps from pure Python with minimal boilerplate.

---

## Zip Structure

Your final zip should look like this (flat structure preferred):

```
my-app.zip
├── app.py              ← main entry point
├── requirements.txt    ← Python dependencies (pinned versions preferred)
├── README.md           ← optional but helpful for the security reviewer
└── (any other .py, .json, .csv files your app needs)
```

**Do not include:**
- `.env` files or any file containing secrets
- `node_modules/`, `__pycache__/`, `.git/` directories
- Virtual environment folders (`venv/`, `.venv/`)
- Files over 50 MB

---

## Dependency Guidance

The GatekeeperAI security scanner checks dependencies. To avoid unnecessary scan findings:

```
# Good — pinned versions
streamlit==1.40.0
openai==1.30.0
pandas==2.2.2

# Avoid — unpinned (scanner flags as unverifiable)
streamlit
openai>=1.0
```

**Flag for the security reviewer, don't omit:** If your app genuinely needs a dependency with known CVEs (rare but happens), include a `README.md` explaining why. Reviewers can approve LOW and MEDIUM findings with context.

---

## Minimal Working Examples

### Streamlit app (recommended starting point)
```python
# app.py
import streamlit as st
import os

st.title("My Internal Tool")

# User is already authenticated by GatekeeperAI
user_email = st.context.headers.get("X-GK-User-Email", "teammate")
st.write(f"Welcome, {user_email}")

# Secrets are injected as env vars — configure in GK Secrets Manager
api_key = os.environ.get("MY_API_KEY", "")

user_input = st.text_area("What would you like help with?")
if st.button("Submit") and user_input:
    st.write("Processing...")
    # your logic here
```

```
# requirements.txt
streamlit==1.40.0
```

### Flask API app
```python
# app.py
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    user = request.headers.get("X-GK-User-Email", "unknown")
    return f"<h1>Hello, {user}</h1>"

@app.route("/api/process", methods=["POST"])
def process():
    data = request.json
    # your logic here
    return jsonify({"result": "done"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

---

## Streamlit API Version Notes

Pin to **`streamlit==1.40.0`** (or higher). Some APIs were added in later versions:

| API | Minimum version | Notes |
|-----|----------------|-------|
| `st.context.headers` | 1.37 | Use to read `X-GK-User-*` headers |
| `st.image(..., use_container_width=True)` | 1.37 | Use `use_column_width=True` on older versions |
| `st.connection()` | 1.28 | Built-in database/API connectors |

If your app fails to start after deployment, GatekeeperAI will show you the container error log directly on your dashboard. The most common cause is a version mismatch between your pinned dependency and an API your code calls.

---

## Tips for a Clean First Scan

- **No secrets in code.** Use `os.environ` and configure values in GK Secrets Manager.
- **Pin your dependencies.** `streamlit==1.35.0` not `streamlit`.
- **Include a README.md** describing what the app does — helps the security reviewer approve it faster.
- **Keep it focused.** Apps that do one thing clearly scan and get approved faster than sprawling multi-feature apps.
- **Don't bundle datasets with PII.** If your app needs data, fetch it from a source at runtime rather than including it in the zip.

---

## Quick Reference Card

```
✓ DO                              ✗ DON'T
─────────────────────────────     ──────────────────────────────
Use os.environ for secrets        Hardcode API keys or passwords
Read X-GK-User-* headers          Build your own login system
Pin dependency versions           Leave versions unpinned
Write a README.md                 Include .env files in the zip
Use Streamlit for simplicity      Build a custom auth middleware
Keep the zip flat and clean       Include node_modules or venv
```

---

*GatekeeperAI is AI-agnostic — use this file with Claude, ChatGPT, Gemini, Grok, GitHub Copilot, or any other assistant. The goal is always the same: describe your problem, let the AI write the app, submit the zip, and GatekeeperAI handles the rest.*

*Docs: [github.com/jacobthomasmichael/GatekeeperAI](https://github.com/jacobthomasmichael/GatekeeperAI)*
