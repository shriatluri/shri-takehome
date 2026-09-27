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

## 2026-09-27 — `cases.rule_version` is the highest policy version in force

**Decision:** a single integer per case, equal to `max(version)` over the rules in force when
the case was scored.

**Alternative:** a jsonb snapshot of the five rule values used.

**Reason:** scenario 5 is written in terms of "version 1" versus "version 2", and a scalar
renders directly in the queue. `policy_rules` still holds every historical value with its
`valid_from` / `valid_to`, so the exact values behind a case remain recoverable.

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
