# KYC Review Queue

A prototype internal tool for a Series C fintech, built as code instead of in Microsoft
Power Apps. A KYC review queue on top of a reusable internal-tools template: mock identity,
Postgres row-level security, server-side field masking, and a hash-chained audit log.

- [`DESIGN.md`](./DESIGN.md) — what we are building and why
- [`PLAN.md`](./PLAN.md) — the PR-by-PR build plan
- [`DECISIONS.md`](./DECISIONS.md) — decision log

Nothing runs yet; see `PLAN.md` PR 1 for the first milestone (`docker compose up` giving a
seeded database).
