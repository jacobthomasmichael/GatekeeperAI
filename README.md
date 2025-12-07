# GatekeeperAI

GatekeeperAI is an internal workflow assistant that orchestrates **access and operational requests** inside large organizations.

Think of it as **“RFPIO for internal processes”**:

- A person needs something done (e.g., *“Create a service account for Superblocks with read-only access to X database”*).
- GatekeeperAI captures the request in a structured form.
- It automatically:
  - Routes the request to the right owners/teams.
  - Creates/updates Jira tickets as needed.
  - Tracks status and required actions across teams.
- Requesters see everything in a **simple, centralized dashboard**.

## POC Goals

The initial proof-of-concept (POC) focuses on:

1. **Data model in Postgres (Neon)**
   - `request_types`
   - `requests`
   - `request_steps` / `request_actions`
   - `routing_rules` (who/what gets notified or assigned)

2. **Superblocks-based “Internal Request Hub”**
   - Form to submit a new request (e.g., “Create DB service account for Superblocks”).
   - Workflow to:
     - Persist the request to Postgres.
     - Call Jira Cloud APIs to create a ticket.
     - Record per-step actions (approvals, tasks, etc.).
   - “My Requests” page to track status and action items.

3. **Jira Integration**
   - Use Jira Cloud (free tier sandbox) for:
     - Ticket creation.
     - Status updates.
     - Assignment / basic workflow.
   - Sync back to Postgres so Superblocks can display up-to-date status.

4. **MVP Dashboard**
   - Requester view:
     - All their requests.
     - Status per step (e.g., “Security review pending”, “DB team implementing”, “Completed”).
   - Optional admin view:
     - All requests by status, team, or request type.

## Tech Stack (POC)

- **Frontend / Orchestration UI:** Superblocks
- **Database:** Postgres on [Neon.tech](https://neon.tech/)
- **Issue Tracking / Workflow Engine:** Jira Cloud (free sandbox)
- **Repo:** GitHub private repo (`GatekeeperAI`) for:
  - DB schema & seed scripts
  - Integration notes & API examples
  - Architecture diagrams & product docs
  - Potential future backend/API code

## Next Steps

1. Set up Neon Postgres instance and create initial schema (`db/schema.sql`).
2. Stand up a Jira Cloud free sandbox and create:
   - A test project
   - Sample components / labels for routing
3. Configure Superblocks to:
   - Connect to Neon (read/write)
   - Talk to Jira Cloud via REST step (API token + email)
4. Build:
   - “Create Request” page
   - “My Requests” dashboard
   - Background workflow to sync Jira status → Postgres
