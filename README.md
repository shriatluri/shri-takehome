# KYC Review Queue

A KYC review portal for a fintech's compliance team, built as code to replace an internal
Microsoft Power Apps workflow. Customers submit an identity form; the backend runs mock IDV
and sanctions screening, scores the risk, and either activates or rejects the customer or
files a case for review. Analysts work their queue, escalated cases need maker-checker
approval by a second senior, admins version the policy rules and inspect a tamper-evident
audit log.

The KYC app sits on a small reusable internal-tools template: mock Entra-shaped identity,
Postgres row-level security, server-side SSN masking and a hash-chained audit log.

- [`DESIGN.md`](./DESIGN.md) — the original brief and acceptance scenarios
- [`DECISIONS.md`](./DECISIONS.md) — decision log, including every deviation from the brief
- [`CONTEXT.md`](./CONTEXT.md) — what shipped in each PR, and what is deliberately not built
- [`PLAN.md`](./PLAN.md) — the PR-by-PR build plan

## Architecture

React 19 + Vite → FastAPI → PostgreSQL 16, orchestrated by Docker Compose.

- **Identity:** the UI sends `X-Demo-User: <employee id>`; the backend turns it into an Entra
  ID-shaped claim `{sub, name, groups}` and authorizes on `groups` only.
- **Database enforces access:** every request runs in one transaction with
  `set_config('app.user_id', …, true)`, and `FORCE ROW LEVEL SECURITY` policies on `cases`,
  `customers` and `policy_rules` decide which rows exist for that user. The API adds no
  `assigned_to` filter.
- **Two roles:** `kyc_owner` runs migrations and seeding and owns the tables; `kyc_app` is the
  runtime role with explicit grants only — no `DELETE` anywhere, `INSERT`/`SELECT` only on
  `audit_log`.
- **Audit log:** every action writes `sha256(prev_hash || canonical row)` in the same
  transaction; `GET /audit/verify` recomputes the chain.
- **Policy versioning:** editing a rule closes the current row and inserts version + 1; each
  case stores the `policy_snapshot` it was scored under.

```
backend/app/platform/   reusable template: identity, DB sessions, masking, migrations, audit
backend/app/apps/kyc/   KYC app: submission pipeline, mock vendors, scoring, decisions, policy
backend/app/demo/       demo-only: employee list and sign-in for the user switcher
frontend/src/{platform,apps/kyc,demo}/   same split
db/migrations/          numbered SQL, applied on startup; db/seed/ synthetic seed data
```

## Run it

```bash
docker compose up --build
```

- UI: http://localhost:5173
- API health: http://localhost:8000/healthz (liveness only, returns `{"status": "ok"}`)

The backend applies migrations on startup and loads seed data if the database is empty. There
is no reset endpoint or button; `docker compose down -v` starts from an empty volume.
Credentials in `docker-compose.yml` are demo values.

## Tests

```bash
docker compose up -d db
cd backend
pip install -r requirements.txt
DB_HOST=localhost pytest -q
```

60 tests, all against a real Postgres (RLS and role grants do not exist in SQLite). The suite
uses its own `kyc_test` database, so it will not disturb a demo in progress. CI runs the same
suite plus the frontend build (`cd frontend && npm ci && npm run build`) on every PR. There
are no frontend or end-to-end tests.

Each acceptance scenario in `DESIGN.md` §8 is proven by a named test:

| # | Scenario | Test |
|---|---|---|
| 1 | Clean submission → Active, no case | `test_kyc_pipeline.py::test_a_clean_submission_is_activated_without_a_case` |
| 2 | Blurry document → Open case, analyst approves, customer Active | `test_review_queue.py::test_scenario_2_analyst_approves_an_open_case` |
| 3 | Near-sanctions name → Escalated, recommender cannot approve, senior does | `test_review_queue.py::test_scenario_3_maker_checker_on_an_escalated_case`, `test_a_senior_cannot_approve_their_own_recommendation` |
| 4 | Fake document → Rejected, no case | `test_kyc_pipeline.py::test_a_fake_document_is_rejected_without_a_case` |
| 5 | Policy edit re-versions, old cases keep version 1 | `test_admin.py::test_scenario_5_a_new_threshold_binds_new_cases_only` |
| 6 | Operations opens the queue → blocked | `test_review_queue.py::test_scenario_6_operations_is_blocked_from_every_queue_route` |
| 7 | Analyst queries `cases` as the app role → only assigned rows | `test_review_queue.py::test_scenario_7_an_analyst_reaches_only_their_own_cases` |

The rest of the suite covers the rules those depend on: RLS asserted in raw SQL as `kyc_app`,
SSN masking, round-robin assignment, the expiring-document score, the audit chain breaking on
edit or delete, and the runtime role's grants.

## Demo walkthrough

Pick a user top-right; the switcher stands in for an Entra ID login. **New submission** is
the customer's own form, so it is available whoever is signed in and answers only "Received".

1. **Blurry document** (any name, country `United States`) → scores 30, files an Open case,
   round-robin assigned. Sign in as that analyst, open the case, Approve → customer Active.
2. **Near-sanctions name** — `Casee Lindquist`, clear document → 93% match against the seeded
   list, Escalated. Any compliance user recommends; that person is then refused the decision
   and a different compliance senior has to approve.
3. **Fake document** → customer Rejected, no case. **Clear document, non-listed name, low-risk
   country** → Active, no case.
4. **Owen Park (operations)** → no queue: the route answers 403 and RLS matches no rows.
5. **Priya Raman (admin)** → no queue, two oversight screens. On **Policy rules** publish
   `escalate_above` = 50: version 2 opens, a new submission scoring 55 is Escalated, and the
   seeded case that scored 55 still shows version 1 in its snapshot. On **Audit log**, filter
   by action and hit **Verify chain**.
6. **Alice vs. Ben** → each analyst sees only their own cases. A senior can reassign a case,
   and it leaves the old analyst's queue on the next poll.

Seed rules: `auto_approve_below` 30, `escalate_above` 70, `sanctions_match_threshold` 85,
`doc_expiry_window_days` 30, `high_risk_countries` Sanctara, Volgaria, Norsavia, Kestrelia.
Score weights: high-risk country 25, Needs-review IDV 30, sanctions match 60, document
expiring inside the window 15.

## Seeded identities

| Name | Team | Level | Sees |
|---|---|---|---|
| Alice Chen | compliance | analyst | Review queue — own cases, masked SSN |
| Ben Ortiz | compliance | analyst | Review queue — own cases, masked SSN |
| Dana Whitfield | compliance | senior | Whole queue, full SSN, can reassign and approve escalations |
| Marcus Lee | compliance | senior | Whole queue, full SSN, can reassign and approve escalations |
| Priya Raman | admin | senior | Policy rules and Audit log; no queue, no customer data |
| Owen Park | operations | analyst | Nothing but the submission form |
