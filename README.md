# KYC Review Queue

A prototype internal tool for a Series C fintech, built as code instead of in Microsoft
Power Apps. A KYC review queue on top of a reusable internal-tools template: mock identity,
Postgres row-level security, server-side field masking, and a hash-chained audit log.

- [`DESIGN.md`](./DESIGN.md) — what we are building and why
- [`PLAN.md`](./PLAN.md) — the PR-by-PR build plan
- [`DECISIONS.md`](./DECISIONS.md) — decision log
- [`CONTEXT.md`](./CONTEXT.md) — session-by-session log of what is built and what is next

## Running it

```bash
docker compose up
```

- API: http://localhost:8000 (`/healthz` reports a row count per table)
- UI: http://localhost:5173
- Postgres: 127.0.0.1:5432 (bound to loopback only)

The backend applies migrations on startup and loads seed data if the database is empty, so a
first `docker compose up` gives a seeded database with no extra steps. Credentials in
`docker-compose.yml` are demo values; nothing here is meant to leave a laptop.

## Walking the demo

Pick a user bottom-left; that switcher stands in for an Entra ID login. **New customer
submission** is the customer's own signup form, so it works whoever is signed in.

- **A blurry document** → the submission scores 30, files an Open case, and round-robin
  assigns it. Sign in as that analyst, open the case, Approve — the customer goes Active.
- **A name close to a sanctions entry** (try `Casee Lindquist`) → an Escalated case. Any
  compliance user recommends; the same person is then refused the decision and a second
  compliance senior has to approve it.
- **Owen Park (operations)** → no queue. The route answers 403 and the RLS policies match no
  rows either.
- **Alice vs. Ben** → each analyst sees only their own cases, and the same is true in `psql`
  as `kyc_app` with `app.user_id` set. The API adds no `assigned_to` filter; the database is
  the only thing enforcing it.

## Database roles

| Role | Used by | Privileges |
|---|---|---|
| `kyc_owner` | migrations and seeding | owns every table |
| `kyc_app` | the API at runtime | explicit grants only; owns nothing |

`kyc_app` owning nothing is what makes `FORCE ROW LEVEL SECURITY` meaningful — an owner can
bypass its own policies. It has no `DELETE` anywhere, and only `INSERT` and `SELECT` on
`audit_log`, which is what makes the log append-only for the application.

## Migrations

Numbered plain SQL in `db/migrations/`, applied in filename order and recorded in
`schema_migrations`. Files ending in `.tmpl.sql` are formatted with the database identifiers
before they run, which is how the runtime role name and password reach `CREATE ROLE` and
`GRANT` without being hardcoded.

Seed data lives in `db/seed/`. The files truncate before inserting, so replaying them restores
the demo state; that is what the demo reset button will call.

## Tests

```bash
cd backend
pip install -r requirements.txt
DB_HOST=localhost pytest
```

Tests run against a real Postgres, not SQLite: row-level security and role grants are the
things being tested, and neither exists in SQLite. They use their own `kyc_test` database
(created on first run, override with `TEST_DB_NAME`) because the suite reseeds and the seed
truncates — so running them will not disturb a demo in progress. CI runs the same suite
against a Postgres service container on every PR.

## Layout

```
backend/app/platform/   reusable template: identity, roles, RLS helpers, masking, audit
backend/app/apps/kyc/   KYC-specific logic: submission pipeline, mock vendors, scoring
backend/app/demo/       demo-only: user switcher, reset
frontend/src/{platform,apps/kyc,demo}/
db/migrations/          numbered SQL, applied on startup
db/seed/                synthetic seed data
```

A new internal app should need only a new `apps/<name>/` folder and no changes to `platform/`.
