# Validation results

Executed locally on Windows on 9 October 2026 against the isolated `ImpactLink/mvp` implementation.

| Check | Result |
| --- | --- |
| Backend `python -m pytest -q` | **15 passed**, 3.81 seconds on final run |
| Frontend `npm run build` | **Passed**, Next.js 15.5.27; production compilation and TypeScript validation succeeded |
| Browser `npx playwright test` | **4 passed**, 22.2 seconds on final run, installed Chrome, one worker |
| `npm audit --audit-level=moderate` | **0 vulnerabilities** reported |
| Editor diagnostics | **No errors found** in the MVP folder |
| SQLite Alembic upgrade and seed | **Passed**, clean database created and seeded; subsequent startup correctly skipped re-seeding |
| Backend health and frontend HTTP | **Passed**, API healthy with demo enabled and AI disabled; frontend returned HTTP 200 |
| Desktop visual inspection | **Passed**, project directory checked at 1440 × 1000 |
| Mobile visual inspection | **Passed**, project directory checked at 390 × 844; no horizontal overflow in browser test |
| PostgreSQL / Docker Compose | **Not executed**; Docker and PostgreSQL were unavailable on this machine |

## Backend coverage

- Valid project and resource-offer creation; invalid quantities rejected.
- Calculated score of 95 for a 15-of-20 offer with full eligibility and other components equal to one.
- Partial coverage, multi-contributor coverage, empty matching results, and cross-requirement capacity accounting.
- Wrong units, missing skills, date conflicts, inactive offers, missing coordinates and service-radius exclusions.
- Explicit acceptance, no reservation on proposal/request, and separate confirmed/delivered totals.
- Two concurrent acceptance attempts against one capacity pool: exactly one succeeded and the other returned HTTP 409.
- Delivery upper bounds and monotonic cumulative quantities.
- Ownership and role checks, duplicate-request rejection, declining, stale-capacity rejection and suspension filtering.
- Cancellation preserves deliveries, releases undelivered commitments, and removes cancelled requirements from unmet-resource metrics.
- Password registration/login/logout and exclusion of real registered accounts from demo login.
- Funding and volunteer units remain separate; estimated beneficiaries never enter verified-outcome totals.
- A suspended organization cannot clear its own suspension by editing its profile. NGO users cannot replace administrator-reviewed outcome evidence.
- AI-disabled health status and operational manual structured entry.

## Browser coverage

1. **Judge journey:** NGO demo login → create a funding project → calculate matches → request → switch to the matching contributor → accept → record partial delivery → reload and verify persistence → open impact analytics. No uncaught browser runtime errors were observed in this journey.
2. **Mobile:** open navigation at 390px → navigate to impact dashboard → search projects → verify results and no horizontal overflow.
3. **Contributor:** create an offer → edit its capacity → deactivate → verify persisted inactive status.
4. **NGO and administrator:** create a project with two distinct resource requirements → verify both rows → switch to administrator → change an organization's review status → restore its initial status.

Browser tests intentionally leave explicitly labelled `Browser journey`, `Browser multiple needs`, and `browser-offer-*` records in the fictional local dataset. Thus current project counts exceed the original 30 seeded projects; dashboard numbers are still computed from records. Tests do not erase existing demo work.

One backend test-library deprecation warning is emitted by Starlette's AnyIO compatibility alias. Playwright also prints a terminal colour-environment warning. Neither caused test failure.

## Reproduction and limits

Use the commands in [README.md](README.md). The local app runs at [localhost:3017](http://localhost:3017), with [OpenAPI documentation](http://localhost:8017/docs). Local records are persisted in SQLite. The PostgreSQL transaction path and Docker startup are supplied but were not claimed as tested. No external LLM, payment processor, or real-world verification integration is connected.
