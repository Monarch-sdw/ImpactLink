# ImpactLink

**Connecting Resources to Real Needs** · SDG 17 · Team De-zum · TS-036

Methodist College of Engineering and Technology, Hyderabad. Shaik Muhammed Muzakir, Mohammed Muabbir Sayeed, and Devansh Bohra.

This is an operational local hackathon MVP with Next.js App Router, TypeScript, Tailwind, a shadcn-style Radix button, Lucide, Recharts, React Hook Form/Zod, FastAPI, SQLAlchemy, and Alembic. It runs locally on SQLite because Docker/PostgreSQL are not installed on the development machine. A PostgreSQL Docker Compose setup is included but has not been executed here.

This copy lives in `ImpactLink/mvp` to isolate it from another implementation that appeared in the parent folder during development. Run commands from **this directory**. The parent's frontend, backend, and database are independent and should not be mixed with this copy.

## Quick start on Windows

Prerequisites: Python 3.12+, Node.js 20.9+ (Node 24 LTS was used), npm, and PowerShell. Restart the terminal after installing runtimes so PATH is refreshed.

```powershell
cd C:\Users\moham\Downloads\ImpactLink\mvp
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -Setup
```

Open **http://localhost:3017**. FastAPI docs: **http://localhost:8017/docs**.

The script installs dependencies into this project's virtual environment, applies migrations, seeds an empty database, generates an ignored local signing secret, and starts two hidden background processes. Ports 3017 and 8017 avoid conflicts with the separate application in the parent folder. Logs and process IDs are in `.runtime/`. On subsequent starts, omit `-Setup`.

```powershell
powershell -ExecutionPolicy Bypass -File .\stop-local.ps1
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

If startup reports occupied ports, check whether this application is already running. The stop script only stops the saved processes after checking their command lines. All records persist in `backend/impactlink.db` across restarts and page refreshes.

## Manual setup (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
Copy-Item .env.example .env
# Replace JWT_SECRET in .env with a random secret.
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8017
```

In a second terminal:

```powershell
cd C:\Users\moham\Downloads\ImpactLink\mvp\frontend
npm ci
$env:API_URL='http://127.0.0.1:8017'
npm run dev -- --port 3017
```

On Linux/macOS use `python3 -m venv .venv`, `.venv/bin/python`, and `API_URL=http://127.0.0.1:8017 npm run dev -- --port 3017`. Copy the backend environment example, set a signing secret, and run backend commands from `backend/`.

## Three-minute judge demo

1. Open **Login / Demo** and choose **NGO organizer**. These are fictional accounts; no passwords are shown or needed.
2. Open **Digital futures: a classroom for everyone** from Overview.
3. Select **Find matching partners**. Inspect scores, explanations, proposed allocations, and the **Partnership network** tab.
4. Send a partnership request to a contributor. Notice that the project still has **zero committed** until acceptance.
5. Select **Demo guide & accounts** and choose the contributor whose organization name appeared on the request. Every seeded offer owner has a demo account.
6. Open **Partnerships**, accept the request, then record a cumulative delivered quantity. Inspect **Impact dashboard** to see committed and delivered values separately.
7. Switch back to the NGO organizer and reopen the project. The updated requirement totals persist after refresh.

The same workflow supports all four demo scenarios. Flood relief has insufficient transport; healthcare has missing qualified volunteers and equipment. These shortages are calculated from the actual records. If judges consume existing capacity, later match plans change accordingly. Create additional offers to explore alternative allocations.

Demo access requires `DEMO_MODE=true`. It is a local, trusted demonstration convenience including an administrator account. Keep it disabled for a non-demo deployment and do not mix real sensitive information into a publicly accessible demo database. Ordinary registration and password login also work; passwords use Argon2 and sessions use HttpOnly cookies. Registration cannot grant administrator privileges.

## Implemented workflows

- Public landing page, searchable project directory with SDG/resource/location/urgency/status filters, project detail pages and organization-scoped overview.
- Registration of NGO, CSR, college/group, and supplier organizations, password login/logout, session validation and fictional account switching.
- NGO project creation with multiple validated requirements; title/description/progress edits; cancellation and completion controls. Completion requires delivery of all requested resources.
- Contributor offer creation, editing, deactivation, available capacity and matching project discovery.
- Deterministic ranked matching and explanations, a combined resource proposal, missing-resource detection, and an interactive connected network view.
- Request, accept, decline, and delivery workflows with ownership checks and transactional capacity revalidation.
- Platform analytics with two Recharts charts. Money and people are never summed together. Recommendations, commitments, delivery and verified outcomes are separate.
- Administrator organization review with audit records, suspension from matching, and outcome attestation requiring an evidence reference.
- OpenStreetMap location links based on stored coordinates.
- Ninety fictional organization profiles (50 NGOs, 20 companies, 10 colleges/groups, 10 community suppliers), 100 anonymous fictional volunteer profiles, 30 projects and 14 resource offers. Volunteer profiles are sample records; capacity is managed through group offers.

## Matching and allocation

The engine in [matching.py](backend/app/matching.py) rejects inactive or exhausted offers, wrong categories or units, missing mandatory specification tags, insufficient date-window coverage, suspended organizations, and offers outside their radius. Missing coordinates exclude local offers instead of inventing a distance. Funding and explicitly remote offers are location-independent. Medical resources and healthcare-tagged volunteering require manual organization verification. Other pending organizations can match with reduced verification weight.

Eligible scores use:

`100 × (0.35 compatibility + 0.20 capacity + 0.20 availability + 0.15 proximity + 0.10 verification)`

- Compatibility: 1 for a supported project SDG; 0.7 for a compatible resource without the cause preference. Mandatory tags are exact, normalized matches, not fuzzy guesses.
- Capacity: available capacity / remaining need, capped at 1.
- Availability: 1 after full date-window eligibility.
- Proximity: `1 − distance / service radius`, bounded at zero; 1 for remote/funding. Haversine distance uses stored coordinates.
- Verification: 1 for manual approval; 0.3 for pending review. Demo verification is simulated and labelled.

Weights are prototype assumptions, not scientifically validated success probabilities. Urgency never inflates suitability. Ties break by offer ID. Each requirement is filled in descending score order, without exceeding its remaining need. An in-memory reservation ledger also prevents the same offer being over-proposed across multiple requirements in one plan. Proposals never reserve actual capacity.

Acceptance reruns eligibility inside a database transaction. PostgreSQL uses a transaction-scoped advisory lock shared by all capacity-changing actions; SQLite uses `BEGIN IMMEDIATE`. It rechecks remaining requirement and uncommitted offer capacity before inserting a unique commitment. Delivery totals can only increase up to the confirmed quantity. Cancelled projects release undelivered allocations and preserve recorded deliveries.

## Data model and API

Models are in [models.py](backend/app/models.py). The Alembic initial revision uses a frozen schema snapshot so future model edits do not change migration history. Tables: organizations, users, projects, requirements, offers, partnerships, commitments, project_updates, verification_records, recommendations, and volunteers. Foreign keys, uniqueness constraints, quantity checks, timestamps, and lookup indexes are included.

For MVP simplicity, a project has one primary SDG and small arrays of supported SDGs/skills are stored in JSON columns. The core operational entities are relational. Quantities use floating-point storage with bounded input; this is a pledge-tracking prototype, not financial accounting or payment processing.

Open [FastAPI documentation](http://localhost:8017/docs) for routes and validation schemas. Organization creation is atomic with registration. Offer deactivation and project cancellation serve as safe removal operations; historical commitments are retained. Organization updates reset verification. User-owned endpoints require matching organization IDs and roles. The frontend proxies `/api/*` to FastAPI so browser cookies stay same-origin.

## PostgreSQL and Docker

Install Docker Desktop with Compose, then:

```powershell
Copy-Item .env.example .env
# Set POSTGRES_PASSWORD and JWT_SECRET to random values in .env.
docker compose up --build
```

Open http://localhost:3000 and http://localhost:8000/docs. PostgreSQL data persists in a named volume. The backend applies Alembic migrations and seeds only an empty organization table. To use an existing PostgreSQL server, set the backend `DATABASE_URL` to `postgresql+psycopg://...` and apply migrations before startup. Use URL-safe database passwords in the Compose example, or URL-encode special characters in the connection URL.

Docker and PostgreSQL integration are supplied but **not runtime-tested on this machine**. The SQLite transaction path is exercised by concurrency tests. For public deployment, disable demo access, use HTTPS with `COOKIE_SECURE=true`, configure trusted origins, provision an administrator through a controlled process, and add operational controls such as throttling and backups.

## Tests and checks

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
npm run typecheck
npx playwright test
```

Browser tests expect the local app on port 3017 and use installed Google Chrome. Set `TEST_URL` to override the URL. They create clearly named browser-test projects and small funding commitments in the local demo database; they do not reset or erase existing records. Backend tests each use a separate temporary SQLite database.

Backend tests cover creation, exact/partial/multi-partner matching, no matches, conflicting dates, inactive/wrong-unit/wrong-skill/distant offers, missing coordinates, concurrent overbooking, acceptance, decline, delivery bounds, ownership, registration/login, stale capacity, cancellation, funding/volunteer metrics and the AI-disabled path. Browser tests cover the judge journey and mobile navigation/filtering. See [VALIDATION.md](VALIDATION.md) for actual results from this build.

## Deliberate prototype limits

- No external LLM or embedding service is connected. Manual structured entry and deterministic matching are fully operational. There is no API-key field that pretends otherwise; natural-language extraction remains optional future work.
- No payment gateway, emails, real-world identity validation, beneficiary PII, or external donation verification. Delivery and evidence are recorded by authorized users, not independently proven by integrations.
- Maps open OpenStreetMap; an embedded Leaflet map is not included.
- Requirements are immutable after project creation to protect linked requests. Create a new project for materially different quantities or dates. Existing requests cannot be renegotiated or resent against the same offer/requirement pair; create an updated offer if needed.
- Capacity represents a finite offered pool, not a recurring calendar inventory. Delivered capacity stays consumed. Greedy allocation is deterministic, not a global optimization across projects.
- Suggested-match statistics count saved unique recommendation pairs, including historical ones; they are never reported as partnerships. Beneficiary verification means a stored manual attestation, and demo attestations remain fictional.
- No production-scale pagination, volunteer-level scheduling, or automated document-verification workflow.

