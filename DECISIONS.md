# Decisions

One entry per meaningful choice: decision, alternative considered, reason.

## 2026-09-27 — Plain SQL migrations over Alembic

**Decision:** numbered `.sql` files in `db/migrations/`, applied by a small runner that
records applied versions in a `schema_migrations` table.

**Alternative:** Alembic.

**Reason:** the schema is small and fixed, and the interesting parts (roles, grants, RLS
policies, `FORCE ROW LEVEL SECURITY`) are clearer as literal SQL a reviewer can read than as
generated Python. Also avoids a dependency outside the agreed list.

## 2026-09-27 — Single app role plus `SET LOCAL app.user_id` over one DB role per employee

**Decision:** the backend connects as one non-owner role (`kyc_app`) and sets
`app.user_id` per transaction; RLS policies read it via `current_setting`.

**Alternative:** a Postgres role per employee, with RLS keyed to `current_user`.

**Reason:** matches `DESIGN.md` §3, keeps connection pooling usable, and still enforces
access in the database. `SET LOCAL` scopes the setting to the transaction so a pooled
connection cannot leak identity between requests.

## 2026-09-27 — Suspension is a decision outcome, not a side effect

**Decision:** reviewing a Needs-review case offers Approve / Reject / Suspend. Suspend sets
the customer to `Suspended` and moves the case to a `Suspended` status, so `cases.status` and
`cases.recommendation` gain `Suspended` / `Suspend` beyond `DESIGN.md` §4.

**Alternative:** set the customer to `Suspended` while leaving the case `Open` in the queue.

**Reason:** `account_status` already allows `Suspended` but no scenario reached it, and a case
waiting on the customer is not work an analyst can pick up — leaving it `Open` would make the
queue lie about what is actionable. Suspension is reversible, unlike Rejected, so a later PR
can reopen the case when a better document arrives.

## 2026-09-27 — Store `document_quality` on the customer

**Decision:** `customers.document_quality` (Clear / Blurry / Fake) is persisted next to the
`idv_status` the mock vendor derived from it.

**Alternative:** treat it as a transient input to the IDV call, since §4 only lists the verdict.

**Reason:** the quality is the evidence behind the verdict and behind any suspension. Keeping
only `idv_status` would leave a reviewer unable to see why a case exists, and the risk score
cites it as a reason.

## 2026-09-27 — `cases.policy_snapshot` records the rules a case was scored under

**Decision:** each case stores a jsonb map of every rule value in force at scoring time,
`{"escalate_above": {"value": "70", "version": 1}, ...}`.

**Alternative:** a single `rule_version` integer, equal to the highest version in force. This
was the original choice, reverted before any code wrote cases.

**Reason:** the scalar is ambiguous the moment rules are edited independently — edit
`escalate_above` to v2, then `auto_approve_below` to v2, and cases scored under two different
policies both read "version 2". The snapshot makes a decision self-explaining without joining
back to `policy_rules` and reasoning about `valid_from` windows. Scenario 5 still reads as
version 1 versus version 2 because the per-rule version travels inside the snapshot.

## 2026-09-27 — `kyc_app` gets column-level UPDATE on `policy_rules`

**Decision:** `GRANT SELECT, INSERT ON policy_rules` plus `GRANT UPDATE (valid_to)`, rather
than table-wide UPDATE.

**Alternative:** table-wide UPDATE, with the append-only versioning enforced in application
code.

**Reason:** publishing a version only ever closes the current row and inserts the next, so
that is the only privilege the runtime role needs. Table-wide UPDATE would let a compromised
session rewrite the values earlier decisions were made under — the same argument that keeps
`audit_log` at INSERT/SELECT.

## 2026-09-27 — Tests run against their own database

**Decision:** the suite redirects `DB_NAME` to `<database>_test`, creating it if absent.

**Alternative:** run against the same database as `docker compose up`.

**Reason:** the suite reseeds and the seed truncates, so sharing a database would erase
whatever a demo is partway through, audit history included.

## 2026-09-27 — Round-robin case assignment with senior reassignment

**Decision:** new cases are auto-assigned round-robin across compliance analysts at creation;
a senior can reassign from the case page.

**Alternative:** leave cases unassigned until a senior claims or assigns them.

**Reason:** `DESIGN.md` §5 gives analysts visibility only into their own cases, so unassigned
cases would be invisible to the people meant to work them and would stall the demo. Auto-assign
keeps the queue live; senior reassignment covers load balancing and is itself an audited action
that visibly changes RLS visibility.

## 2026-09-27 — Sequential PRs on `main` over a stacked series

**Decision:** each PR branches from `main` and merges before the next session starts.

**Alternative:** a stack of dependent PRs.

**Reason:** the build plan is strictly layered (foundation → template → app), each PR is
meant to be reviewable in a few minutes, and sequential merges keep the demo runnable at
every step.

## 2026-09-27 — `audit_log` is append-only by grant, admin-only by route

**Decision:** `kyc_app` holds `SELECT, INSERT` and no `UPDATE`/`DELETE` on `audit_log`, and
no RLS policy is attached. "Only admin reads the log" is enforced on `GET /audit`.

**Alternative:** an admin-only RLS SELECT policy, which forces the append path through a
`SECURITY DEFINER` function owned by `kyc_owner` so it can still read the previous hash.

**Reason:** every writer needs the tail of the chain to compute `prev_hash`, so strict RLS
buys a definer function and a second privilege boundary for a demo where the property worth
showing is tamper-evidence, not read isolation. The immutability that the hash chain depends
on is the part the database still enforces.

## 2026-09-27 — Anonymous submissions run as a reserved system identity

**Decision:** `app.user_id = 0` identifies the submission pipeline. `app_is_system()` gates
policies that let it insert customers and cases; its audit rows carry `employee_id = NULL`
and the viewer renders that actor as "System".

**Alternative:** a seeded "System" employee row.

**Reason:** the submission form is an unauthenticated customer, not a member of staff. A
seeded employee would appear in the user switcher, in round-robin assignment, and in any
future `employees` listing. Id `0` cannot collide with a serial primary key.

## 2026-09-27 — Coarse RLS on `customers`

**Decision:** compliance (either level) and the system identity can read and write customers;
operations and admin match no policy and see no rows.

**Alternative:** filter customers through the assignments on their cases, so an analyst sees
only the customers behind their own queue.

**Reason:** it would make the visibility of a customer depend on a case that does not exist
yet at insert time, and adds a join to every read for a rule no scenario tests. The demo's
claim is that the database, not a `WHERE` clause, decides — a coarse policy still shows that.

## 2026-09-27 — Full SSN requires compliance *and* senior

**Decision:** `can_see_ssn` is `team = 'compliance' AND level = 'senior'`. Everyone else,
admin included, gets `***-**-1234` from the serializer.

**Alternative:** gate on `level = 'senior'` alone.

**Reason:** the admin is `level = senior`, so the level check alone would hand unmasked SSNs
to the one role `DESIGN.md` §5 gives no customer access at all. Masking happens in
serialization, so no route can leak a full SSN by forgetting to call a helper.

## 2026-09-27 — Local-state navigation over `react-router-dom`

**Decision:** pages are a `Page[]` filtered by claim groups, with the current page in
`useState`.

**Alternative:** add `react-router-dom`.

**Reason:** four pages, no deep links or nested layouts in scope, and the dependency is
outside the agreed list. The role filtering is the part worth having, and it is the same
either way.
