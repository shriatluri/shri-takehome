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

## 2026-09-27 — Sequential PRs on `main` over a stacked series

**Decision:** each PR branches from `main` and merges before the next session starts.

**Alternative:** a stack of dependent PRs.

**Reason:** the build plan is strictly layered (foundation → template → app), each PR is
meant to be reviewable in a few minutes, and sequential merges keep the demo runnable at
every step.
