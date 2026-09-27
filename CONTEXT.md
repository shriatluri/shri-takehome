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

## Last session (most recent)

### Session 2 — foundation (PR [#2](https://github.com/shriatluri/shri-takehome/pull/2))

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

## Next session

**PR 2 — platform controls** (`backend/app/platform/`, per `PLAN.md`):

1. Mock identity shaped like Entra ID claims (`X-Demo-User` header → employee), plus the
   frontend user switcher.
2. RLS policies with `FORCE ROW LEVEL SECURITY`: analysts see only cases assigned to them,
   seniors see the whole compliance queue, operations sees none.
3. Request-scoped `SET LOCAL app.user_id` in `get_session`, so the policies have an identity.
4. Server-side SSN masking — the API never emits full SSNs to a role that cannot see them.
5. Hash-chained audit logger, verified by a test that tampering breaks the chain.

Everything above is platform, not KYC. The pipeline (risk scoring, sanctions matching, case
creation, round-robin assignment) is PR 3, and the review queue UI with maker-checker
approvals and the Suspend decision is PR 4.
