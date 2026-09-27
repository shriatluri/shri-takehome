# Context

Running log so a new session can pick up without re-reading every PR. Newest session last.
Keep entries short: what shipped, what it unblocks, what is next.

- What we are building and why: [`DESIGN.md`](./DESIGN.md)
- The PR-by-PR plan: [`PLAN.md`](./PLAN.md)
- Why things are the way they are: [`DECISIONS.md`](./DECISIONS.md)

## Previous sessions

### Session 1 — planning (PR [#1](https://github.com/shriatluri/shri-takehome/pull/1), merged)

Docs only, no code. Turned `DESIGN.md` into a six-PR plan and started the decision log.
Settled: plain SQL migrations over Alembic, two database roles with `SET LOCAL app.user_id`
per request, sequential PRs rather than a stack, CI pulled forward into PR 1. Asked the one
question the design left open — who assigns cases — and got round-robin at creation with
senior reassignment from the case page.

### Session 2 — foundation (PR [#2](https://github.com/shriatluri/shri-takehome/pull/2), merged)

`docker compose up` now brings up Postgres + FastAPI + Vite, applies migrations, seeds
synthetic data, and serves `/healthz`. No KYC behaviour yet.

- **Roles:** `kyc_owner` owns the tables; `kyc_app` (the API) owns nothing and has explicit
  grants only — no `DELETE` anywhere, `INSERT`/`SELECT` on `audit_log`, `UPDATE (valid_to)`
  on `policy_rules`. Non-ownership is what will make `FORCE ROW LEVEL SECURITY` real in PR 2.
- **Schema:** the six tables from §4 plus `schema_migrations`. Two invariants live in the
  database: `CHECK (approved_by <> recommended_by)` and a partial unique index giving each
  rule exactly one current version.
- **Schema changes agreed this session:** `customers.document_quality` added;
  `Suspended`/`Suspend` added to case status and recommendation; `cases.rule_version`
  replaced by `cases.policy_snapshot` (jsonb) so a decision records the values it used.
- **Seed:** 6 employees, 12 customers across all four account statuses, 15 fictional
  sanctions entries, 5 rules at v1, 4 cases (Open / Escalated / Approved / Suspended).
- **Tests:** 13 pytest tests against real Postgres, in their own `kyc_test` database. CI runs
  them plus a frontend typecheck/build on every PR.

Devin Review on PR #2: fixed the `policy_rules` grant, test-database isolation, a hardcoded
seed expiry date, and the published Postgres port. Declined as not worth the scope: escaping
URL-reserved characters in passwords, rotating the demo credentials, and re-running the role
migration when `DB_APP_PASSWORD` changes.

## Last session (most recent)

### Session 3 — platform controls (PR 2)

The four controls the demo is about now work end to end: pick a user in the switcher and the
queue, the SSN column, and the audit tab all change.

- **Identity:** `X-Demo-User: <employee id>` → `{sub, name, groups: [team, level]}`, an Entra
  ID-shaped claim. Authorization reads `groups` only, so swapping in real Entra means
  replacing the claim source. Unknown or missing header on an app route → 401.
- **Request-scoped session:** `session_scope` issues `set_config('app.user_id', …, true)` —
  transaction-local, so a pooled connection cannot leak identity between requests. A test
  asserts the setting is gone after the transaction ends.
- **RLS (`004_rls.sql`):** `FORCE ROW LEVEL SECURITY` on `cases`, `customers`, `policy_rules`.
  Policies join `employees` through `app_user_id()`, so the database derives team and level
  rather than trusting anything header-derived. Analyst → assigned cases; compliance senior →
  all; operations and admin → none. No identity set means no rows.
- **Masking:** `***-**-1234` in the serializer for everyone but compliance seniors — admin is
  `level = senior` and still gets a masked value.
- **Audit:** `sha256(prev_hash || canonical row)` written in the same transaction as the
  action, serialized on `pg_advisory_xact_lock`. Tampering or deleting a row makes `verify`
  return the first bad id.
- **Frontend:** identity context + user switcher, API client that attaches the header,
  claim-filtered local-state nav, read-only queue page and admin audit page.
- **Tests:** 39 pytest tests against real Postgres (was 13), including RLS asserted in raw
  SQL as `kyc_app`.

Settled this session (details in `DECISIONS.md`): `audit_log` append-only by grant with
admin-only reads at the route rather than RLS plus a definer function; anonymous submissions
run as reserved id `0` with a null audit actor; coarse `customers` policy; full SSN requires
compliance *and* senior; local-state nav instead of `react-router-dom`.

## Next session

**PR 3 — the KYC pipeline** (`backend/app/apps/kyc/`, per `PLAN.md`): the submission form,
mock IDV and sanctions matching, risk scoring against `policy_rules` with a
`policy_snapshot`, case creation and round-robin assignment. It imports the platform layer —
identity, `session_scope`, `audit.record` — and adds nothing to it. The review queue UI with
maker-checker approvals and the Suspend decision is PR 4; `/cases` and the queue page here
are read-only placeholders that PR 4 replaces.
