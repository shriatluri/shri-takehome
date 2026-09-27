---
name: kyc-demo-runtime-testing
description: Run browser-based KYC submission, role visibility, and audit checks against the local Docker demo without reseeding away evidence.
---

# KYC demo runtime testing

## Setup
- Run `docker compose up -d --build` from the repository root. UI is http://localhost:5173; backend is :8000. Migrations and seed run at backend startup.
- Use the Demo controls dropdown rather than real authentication: Alice/Ben are analysts, Dana/Marcus seniors, Priya admin, Owen operations.
- Do not run pytest against the live demo database during UI testing: test fixtures can truncate/reseed and erase the walkthrough state.

## Browser workflow
- Customer submission is always visible, even unsigned and for operations.
- Queue fetches again on identity change or browser reload; clicking an already active Review queue tab does not refresh it.
- Date inputs are segmented in Chromium. Typing two month digits and two day digits advances automatically; explicit Right after each segment can skip fields. Verify the displayed date before submitting.
- Leave document expiry blank to exercise its optional/null path.
- Compare analysts against the assigned case and against the other analyst; compare a senior for full SSN.
- Audit rows expand to show `details` and `prev_hash`; policy snapshots are on the case detail pane. Supplement anything else with read-only database observations.

## Distinguishing test data
- Blurry + Volgaria produces Open/55 for a name not on sanctions.
- Clear + United States with a non-sanctions name activates with no case.
- Fake rejects with no case.
- Check current sanctions seed names and aliases before claiming a fuzzy test: an apparent spelling variation may be an exact list name or alias.
- On the current seed, Casee Lindquist is a genuine 93% match to Casey Lindquist; Clear + United States produces Escalated/60. This also distinguishes sanctions escalation from score-only escalation.
- A browser-entered DOB year 10000 reaches backend date validation: expect 422, Could not submit., retained fields, no new record. Correct the year and retry.

## Devin Secrets Needed
None for the local mock-auth Docker demo. Compose supplies local database credentials.
