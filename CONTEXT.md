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

### Session 4 — KYC pipeline (PR 3)

One vertical slice: submit the form on the page and a scored case appears in an analyst's
queue on the next refresh. Nothing under `backend/app/platform/` changed.

- **Route:** `POST /submissions`, anonymous, running on `session_for(SYSTEM_USER_ID)` so the
  `app_is_system()` policies let it insert. It answers `{"status": "Received"}` and nothing
  else — no case number, no outcome.
- **Mock vendors (`apps/kyc/vendors.py`):** IDV is the `Clear/Blurry/Fake` lookup; screening
  is one `difflib` ratio over `full_name` plus aliases against `sanctions_match_threshold`.
  Deterministic functions over seeded rows, no clients, no `rapidfuzz`.
- **Scoring (`apps/kyc/scoring.py`):** high-risk country 25 + Needs-review IDV 30 + sanctions
  match 60, each with its reason. Reads every current rule and returns it as the snapshot the
  case stores.
- **Pipeline (`apps/kyc/pipeline.py`):** Failed IDV → customer Rejected, no case; under
  `auto_approve_below` with no match → Active, no case; otherwise a case, Escalated on a
  match or above `escalate_above`, else Open — assigned round-robin from the last assignment,
  and one `submission.processed` audit entry either way, in the same transaction.
- **Frontend:** `apps/kyc/SubmissionForm.tsx`, a plain always-visible form. `apiPost` grew an
  optional JSON body; no other frontend platform file changed.
- **Tests:** 5 slice tests (44 total) — case created, scored, assigned and visible to its
  assignee; the sanctions branch and its audit entry; both no-case branches; the rotation.

## Last session (most recent)

### Session 5 — review queue (PR 4)

The queue is now the working half of the demo: submit a case, open it, decide it, and watch
the customer's account status follow. Scenarios 2, 3, 6 and 7 pass. Nothing under
`backend/app/platform/` changed.

- **Routes:** `GET /cases/{id}` (case + customer, masked), `POST /cases/{id}/recommendation`,
  `POST /cases/{id}/decision`, `POST /cases/{id}/assignment`, `GET /reviewers`. All behind
  `require_group("compliance")`, so operations and admin get 403 before RLS is consulted.
- **State machine (`apps/kyc/decisions.py`):** Open → any reviewer who can see it decides.
  Escalated → someone recommends, then a *different* compliance senior decides; the
  recommender is refused 403 and the database's `CHECK (approved_by <> recommended_by)`
  refuses it a second time. Decided cases are final (409). The decision writes the case row,
  the customer's `account_status` and the audit entry in one transaction.
- **Reassignment:** senior-only, target must be on the compliance team, audited — and the
  previous assignee loses the case on their next poll, because the RLS policy is the only
  thing deciding who sees it.
- **Frontend:** design tokens in `index.css` and primitives in `platform/ui.tsx` (card,
  badge, risk dial, drawer, toasts, skeletons) — no UI dependency added. Sidebar shell, queue
  with 5s polling, filter chips, search, clickable rows, and a case drawer with the risk
  breakdown, policy snapshot, maker-checker state and the actions this user may take. The
  submission form moved into a drawer; it still says "Received." and nothing else.
- **Tests:** 10 queue tests (54 total) — approval path, self-approval block, missing
  recommendation, already-decided, operations 403 on every route, analyst 404 on another
  analyst's case, raw SQL as `kyc_app` seeing only assigned rows, reassignment flipping
  visibility, and the audit entries.

## Next session

**PR 5 — policy administration**, per `PLAN.md`: the admin page that versions `policy_rules`
(`valid_to` on the old row, a new row at version + 1) so scenario 5 passes — change
`escalate_above` 70 → 50, submit something scoring ~60, and the new case is Escalated under
version 2 while the older case still shows version 1 in its snapshot. The audit page is also
still the unfiltered 100-row list from PR 2; chain verification belongs there.
