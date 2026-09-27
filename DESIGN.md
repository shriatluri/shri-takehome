# KYC Review Queue: Prototype Design Doc

## 1. Overview

A Series C fintech (~60 engineers) runs 3 internal apps on Microsoft Power Apps and plans 10+ more. This prototype tests whether those tools can be built as code with Devin instead.

We are rebuilding one of their existing apps, the **KYC review queue**, on a **reusable internal-tools template**. It replaces these Power Apps capabilities:

| Power Apps | This prototype |
|---|---|
| Dataverse | PostgreSQL |
| Row/field security | Postgres row-level security + server-side masking |
| Dataverse auditing | Append-only, hash-chained audit log |
| Entra ID login | Mock identity shaped like Entra ID group claims |
| Power Automate approvals | Risk-tiered maker-checker approvals in code |

This is a prototype. Quality over quantity: a small set of features that work correctly and are easy to review beats broad coverage.

## 2. Goals and non-goals

**Goals**
- A working KYC pipeline: customer submits → automated checks → auto-decision or review queue
- Access control enforced by the database, not just the UI
- Five fintech features (section 6) that are hard to do well in Power Apps
- A clean split between reusable template code and KYC-specific code

**Non-goals (do not build)**
- Real Entra ID / OAuth integration
- Cloud deployment
- Calls to real ID verification or sanctions vendors
- A visual rule builder
- Visual polish beyond clean and readable

## 3. Architecture

**Stack:** FastAPI (Python), React (Vite), PostgreSQL. Run everything with Docker Compose (3 containers: db, backend, frontend). `docker compose up` must start the full app with seed data.

**Request flow:** React → FastAPI → Postgres. On every request, the backend sets the current user on the DB session (e.g. `SET app.user_id`) so row-level security applies. The app connects as a non-owner role and tables use `FORCE ROW LEVEL SECURITY`.

**Folder structure**
```
backend/app/platform/   # reusable template: identity, roles, RLS helpers, masking, audit
backend/app/apps/kyc/   # KYC-specific logic
backend/app/demo/       # demo-only: user switcher, submission form, mock IDV, reset
frontend/src/platform/
frontend/src/apps/kyc/
frontend/src/demo/
db/migrations/
db/seed/
```
A new app should need only a new `apps/<name>/` folder. It must not modify `platform/`.

## 4. Data model

Rule: one table per thing with its own lifecycle. Everything else is a column.

| Table | Purpose | Key columns |
|---|---|---|
| employees | Demo users | id, name, team (compliance / operations / admin), level (analyst / senior) |
| customers | People who submitted KYC | id, full_name, dob, country, address, ssn, document_expiry, idv_status (Pending / Passed / Failed / Needs review), idv_reason, idv_checked_at, account_status (Pending / Active / Rejected / Suspended) |
| sanctions_list | Mock sanctions entries | id, full_name, aliases, dob (may be partial), nationality, entity_type, program, list_source, date_added |
| cases | Reviews in the queue | id, customer_id, status (Open / Escalated / Approved / Rejected), risk_score, risk_reasons (list), sanctions_match_id, assigned_to, recommended_by, recommendation, approved_by, decision_reason, rule_version, created_at, decided_at |
| policy_rules | Versioned decision settings (SCD Type 2) | id, rule_name, value, version, valid_from, valid_to (null = current), changed_by |
| audit_log | Append-only action record | id, timestamp, employee_id, action, record_type, record_id, details, prev_hash, hash |

A customer has zero or more cases. Most customers never get one.

All seed data is synthetic. Sanctions entries use obviously fictional names.

## 5. Roles and permissions

| User | Queue access | SSN | Can decide | Admin pages |
|---|---|---|---|---|
| Compliance analyst | Only cases assigned to them | Masked (***-**-1234) | Open cases; can recommend on Escalated | No |
| Compliance senior | All cases | Full | All cases; approves Escalated | No |
| Admin | No | n/a | No | Policy rules, audit log |
| Operations | Blocked (403) | n/a | No | No |

Masking happens server-side. Unauthorized users never receive the unmasked value.

## 6. Fintech features

1. **Explainable risk scoring.** Score each submission from rules and return the reasons, e.g. "Needs review IDV (+30), high-risk country (+25)." Rule values come from `policy_rules`.
2. **Sanctions fuzzy matching.** Compare name (and aliases) against `sanctions_list` using `rapidfuzz`. A match above the sensitivity threshold forces escalation.
3. **Versioned policy rules (SCD Type 2).** Admin edits never overwrite. They close the current row (set `valid_to`) and insert a new version. Each case stores the rule version it was created under. Rule changes affect new submissions only.
4. **Risk-tiered approvals.** Open (medium risk): an analyst decides alone. Escalated (high risk or sanctions match): one person recommends, a different senior approves. Self-approval is blocked in the backend.
5. **Tamper-evident audit log.** Each row stores `hash = sha256(prev_hash + row contents)`. The app role has no UPDATE or DELETE on this table. Provide a verify endpoint that checks the chain.

**Starting rule values**

| rule_name | value |
|---|---|
| auto_approve_below | 30 |
| escalate_above | 70 |
| sanctions_match_threshold | 85 |
| doc_expiry_window_days | 30 |
| high_risk_countries | small fictional-safe list |

**Pipeline:** IDV Failed → customer Rejected, no case. Score below auto_approve and no sanctions match → customer Active, no case. Otherwise create a case: Escalated if score above escalate_above or sanctions match, else Open.

## 7. Demo-only components

These simulate the outside world and are not part of the app. Put them in `demo/` folders and one clearly labeled "Demo controls" area in the UI.

- **User switcher:** dropdown of seeded employees; stands in for Entra ID login
- **Submission form:** stands in for the fintech's customer-facing signup. Fields: name, DOB, country, address, SSN, document expiry, document quality (Clear / Blurry / Fake)
- **Mock IDV vendor:** Clear → Passed, Blurry → Needs review, Fake → Failed
- **Reset button:** restores seed data

The queue page refreshes every 5 seconds so new cases appear during the demo.

## 8. Demo scenarios (acceptance criteria)

| # | Input | Expected result |
|---|---|---|
| 1 | Clean submission, clear document | Customer Active, no case |
| 2 | Blurry document | Open case; analyst approves; customer Active |
| 3 | Name close to a sanctions entry | Escalated case; analyst recommends reject; analyst cannot approve own recommendation; senior approves; customer Rejected |
| 4 | Fake document | Customer Rejected, no case |
| 5 | Admin changes escalate_above 70 → 50, then a submission scoring ~60 | New case is Escalated under version 2; an earlier case with a similar score still shows version 1 |
| 6 | Operations user opens the queue | Blocked |
| 7 | Analyst queries cases via raw SQL as the app role | Sees only assigned cases |

## 9. Build plan

| PR | Contents | Done when |
|---|---|---|
| 1. Foundation | Docker Compose, schema, migrations, seed data, README skeleton, DECISIONS.md | `docker compose up` gives a seeded database |
| 2. Template | Mock identity, roles, RLS, masking, hash-chained audit logger, tests | Each demo user sees the right rows and fields; actions are logged |
| 3. KYC pipeline | Submission form, mock IDV, risk scoring, sanctions matching, case creation | Scenarios 1, 3 (case creation), and 4 pass |
| 4. Review queue | Queue and case pages, approvals, self-approval block, account status updates | Scenarios 2, 3, 6, 7 pass |
| 5. Admin | Policy rules page with versioning, audit log viewer, chain verify | Scenario 5 passes |
| 6. Stretch | Feature-flag admin panel built only in `apps/feature_flags/` using `platform/` | Works with existing roles and audit log, no changes to `platform/` |

## 10. Priorities and stretch goals

**Must not be cut:** RLS, masking, risk-tiered approvals, audit log, scenarios 1–4 and 6–7.

**Cut first if short on time:**
1. Admin rule-editing UI (seed two rule versions instead)
2. Audit chain verify endpoint (keep the hashing)
3. Visual polish

**Stretch:** PR 6; GitHub Actions workflow that runs tests on each PR.

## 11. Constraints and working instructions

- Synthetic data only. No real names, no external network calls, no real credentials.
- Work one PR at a time. Stop after each PR and summarize what changed, what's tested, and anything you were unsure about.
- Write pytest tests for: RLS visibility per role, SSN masking, self-approval block, rule versioning, audit chain integrity.
- Keep `DECISIONS.md` updated. One entry per meaningful choice: decision, alternative considered, reason.
- Prefer simple, readable code over abstraction. A reviewer should understand each PR in a few minutes.
- Don't add dependencies beyond FastAPI, SQLAlchemy/psycopg, rapidfuzz, pytest, React, and Vite without asking.
