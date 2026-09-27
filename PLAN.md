# Build Plan

Execution plan for the KYC Review Queue prototype described in `DESIGN.md`.
One PR per row, built in order, each in its own Devin session. Every PR ends with a
summary of what changed, what is tested, and open questions, plus a `DECISIONS.md` update.

## Ground rules

- Branch per PR off `main`, merged before the next PR starts (no stacking).
- Dependencies limited to: FastAPI, SQLAlchemy/psycopg, rapidfuzz, pytest, React, Vite.
  Anything else is proposed before it is added.
- All data synthetic. No external network calls at runtime.
- `platform/` is the reusable template. `apps/kyc/` may import from it; never the reverse.
  `demo/` simulates the outside world and is clearly separated in code and UI.
- Tests run against a real Postgres (RLS cannot be tested against SQLite).

## PR 1 — Foundation

Scope
- `docker-compose.yml`: `db` (postgres:16), `backend` (uvicorn, hot reload), `frontend` (vite dev server).
- `db/migrations/`: numbered plain-SQL files applied by a small idempotent runner on backend
  startup (tracked in a `schema_migrations` table). No Alembic.
- Schema for all six tables in `DESIGN.md` §4, including enum/check constraints, FKs,
  and the `audit_log` append-only grants.
- Two DB roles: `kyc_owner` (migrations, table owner) and `kyc_app` (runtime, non-owner,
  subject to `FORCE ROW LEVEL SECURITY`). RLS policies themselves land in PR 2.
- `db/seed/`: employees (one per role in §5, two analysts and two seniors so maker-checker
  is demonstrable), ~12 customers with a spread of outcomes, ~15 fictional sanctions entries,
  policy rules at the §6 starting values (version 1), plus a couple of pre-existing cases.
- `/healthz` endpoint, React shell that calls it, README skeleton, `DECISIONS.md`.
- Stretch pulled forward: GitHub Actions workflow running pytest against a Postgres service.

Done when: `docker compose up` yields a seeded database and both services reachable.

## PR 2 — Platform template

Scope
- Mock identity: user switcher sends the employee id on every request
  (header `X-Demo-User`, shaped like an Entra ID group claim: `{sub, name, groups: [...]}`).
- Request-scoped DB session that runs `SET LOCAL app.user_id` inside the transaction so RLS
  and audit both see the caller. No connection leaks the setting between requests.
- RLS policies: analyst sees only `cases.assigned_to = current employee`; senior sees all;
  operations sees none; admin has no queue access but reads `policy_rules`/`audit_log`.
- Server-side masking helper: SSN masked to `***-**-1234` for anyone below senior.
  Masking happens in the serialization layer, never in the frontend.
- Hash-chained audit logger: `hash = sha256(prev_hash || canonical row contents)`,
  written in the same transaction as the action. `kyc_app` has INSERT/SELECT only.
- Frontend `platform/`: identity context, user switcher shell, API client, role-aware routing.

Tests: RLS visibility per role (raw SQL as `kyc_app`), masking per role, audit chain
integrity across a sequence of writes, audit table rejects UPDATE/DELETE.

Done when: each seeded user sees exactly the rows and fields §5 allows; actions are logged.

## PR 3 — KYC pipeline

Scope
- Demo submission form + mock IDV vendor (Clear → Passed, Blurry → Needs review, Fake → Failed).
- Explainable risk scoring in `apps/kyc/`: rules read from the current `policy_rules` version,
  returning `(score, reasons[])` with per-reason point contributions.
- Sanctions fuzzy matching with `rapidfuzz` over `full_name` + aliases, threshold from
  `sanctions_match_threshold`; partial-DOB entries handled explicitly.
- Pipeline per §6: IDV Failed → Rejected, no case; below `auto_approve_below` with no match →
  Active, no case; otherwise create a case (Escalated on high score or sanctions match,
  else Open) stamped with the rule version used.
- New cases are auto-assigned round-robin across compliance analysts at creation.

Tests: scoring reason output, fuzzy match thresholds, pipeline branch table.
Done when: scenarios 1, 3 (case creation) and 4 pass.

## PR 4 — Review queue

Scope
- Queue page (5s polling) and case detail page, both role-aware.
- Decisions: analyst approves/rejects Open cases; on Escalated, one person recommends and a
  different senior approves. Self-approval blocked in the backend, not just hidden in the UI.
- Decisions write customer `account_status` and the audit log in one transaction.
- Operations user receives 403; admin has no queue route.
- Seniors can reassign a case to a different analyst from the case page; the reassignment is
  audited and immediately changes which analyst the RLS policy lets see the case.

Tests: self-approval block, decision state machine, 403 for operations, RLS through the API.
Done when: scenarios 2, 3, 6, 7 pass.

## PR 5 — Admin

Scope
- Policy rules page: edits close the current row (`valid_to = now()`) and insert version + 1.
  Existing cases keep their recorded version; changes affect new submissions only.
- Audit log viewer with filters, plus a chain-verify endpoint reporting the first broken link.

Tests: SCD Type 2 transitions, version stamping on new vs old cases, verify endpoint
detects a tampered row (tamper applied as the owner role in the test).
Done when: scenario 5 passes.

## PR 6 — Stretch

Feature-flag admin app built entirely in `apps/feature_flags/` on top of `platform/`,
proving a new internal app needs no template changes. Verified by a diff touching no
`platform/` file.

## Risks

- RLS correctness is the whole point of the demo; it gets tested at the SQL layer, not only
  through the API.
- Audit hashing must be deterministic across processes — canonical JSON serialization with
  sorted keys and a fixed timestamp format.
- Reset must restore seed data without dropping the migration history mid-demo.
