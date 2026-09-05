# Recoup — Autonomous Revenue Recovery Platform

**Recoup** is an AI-native revenue recovery platform designed to diagnose and resolve payment failures across **B2B invoice cycles** and **consumer recurring billing** (SaaS subscriptions, checkout, and UPI AutoPay / e-mandates).

Instead of sending generic, aggressive debt-collection messages or blindly retrying failed cards, Recoup operates as an assembly line of specialized AI agents that determine **why** a payment failed, formulate a **tailored, compliant recovery strategy**, and bring revenue back while preserving customer goodwill.

---

## Table of Contents

- [Core Value Proposition](#core-value-proposition)
- [Multi-Agent Architecture](#multi-agent-architecture)
- [Key Features & Dashboard](#key-features--dashboard)
  - [1. Executive Recovery Dashboard](#1-executive-recovery-dashboard)
  - [2. Case Operations Command Center](#2-case-operations-command-center)
  - [3. Live Multi-Agent Simulator](#3-live-multi-agent-simulator)
  - [4. Full Chronological Audit Trails](#4-full-chronological-audit-trails)
  - [5. Fair Debt Compliance Gate](#5-fair-debt-compliance-gate)
- [Agent Taxonomies & Guardrails](#agent-taxonomies--guardrails)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quickstart Guide](#quickstart-guide)
  - [Prerequisites](#prerequisites)
  - [1. Start Database & Backend](#1-start-database--backend)
  - [2. Start Frontend Dashboard](#2-start-frontend-dashboard)
- [Simulating & Testing the Agents](#simulating--testing-the-agents)
- [API Reference](#api-reference)
- [Automated Test Suite](#automated-test-suite)

---

## Core Value Proposition

Traditional payment recovery is broken:
- **Blind Retries**: Repeatedly charging cards until banks permanently block transactions.
- **Generic Harassment**: Spamming customers with robotic *"PAYMENT FAILED PAY NOW"* emails that cause churn and damage business relationships.

**Recoup transforms recovery into an intelligent, empathetic workflow:**
1. **Root-Cause Discovery**: Distinguishes between temporary technical glitches, cash crunches, disputes, and forgetfulness.
2. **Tailored Interventions**: Silently retries network glitches without bothering the user; offers installment plans for liquidity distress; and sends courteous reminders for clean-record accounts.
3. **Audit Honesty**: Every agent decision, prompt output, and recovered rupee is tied to an immutable database audit log.

---

## Multi-Agent Architecture

```
                    Payment Failure / Overdue Invoice
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │       1. Root-Cause Diagnosis Agent              │
         │  • Analyzes telemetry, logs, & customer history  │
         │  • Output: Category + Calibrated Confidence %    │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │       2. Intervention Router Agent               │
         │  • Selects optimal channel (Email/WhatsApp/None) │
         │  • Drafts personalized, context-aware outreach   │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │       3. Compliance Guardian Gate                │
         │  • Checks contact limits & broken promise caps   │
         │  • Output: Dispatched OR Blocked for Review      │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼ Customer Replies
         ┌──────────────────────────────────────────────────┐
         │       4. Promise Extraction Agent                │
         │  • Extracts promised settlement date & amount    │
         └─────────────────────────┬────────────────────────┘
                                   │
                                   ▼ Due Date Passes
         ┌──────────────────────────────────────────────────┐
         │       5. Promise Evaluator Agent                 │
         │  • Marks Kept (Recovered) or Broken (Escalated)  │
         └──────────────────────────────────────────────────┘
```

---

## Key Features & Dashboard

### 1. Executive Recovery Dashboard (`/`)
- Real-time KPI counters: **Total Events**, **Amount at Risk**, **Recovered Amount**, and **Recovery Rate**.
- Interactive **Bar Chart** depicting recovery rate breakdown by root cause.
- **Distribution Donut Chart** showing failure share across categories.
- **End-to-End Funnel**: Tracking cases through Diagnosed → Routed → Dispatched → Customer Replied → Promise Made → Revenue Recovered.
- **Honesty Banner**: Transparently documenting proxy metric calculations and simulated vs. confirmed settlements.

### 2. Case Operations Command Center (`/cases`)
- **4 Live KPI Cards**: Pipeline volume, gross capital at risk, average AI confidence, and escalated case count.
- **Instant Client-Side Search**: Filter immediately by Customer ID, Case UUID, or root cause.
- **1-Click Filter Chips**: Quick toggle between *All Sources*, *B2B Invoices*, *Subscriptions*, and *UPI AutoPay*.
- **Executive Data Table**:
  - Customer avatar initials badge + formatted ID.
  - Colored root cause badges with **horizontal micro-confidence bars** (e.g. `85%`).
  - Channel badges with icons (WhatsApp 💬, Email ✉️, Silent Retry ⚡, SMS 📱).
  - Status pills with pulsing live indicators.
  - Direct "Inspect" row actions.

### 3. Live Multi-Agent Simulator (`Modal`)
- Triggered directly from the **`⚡ Ingest & Run Recovery Agent`** button.
- **4 Built-in Scenario Presets**:
  - 🏢 *B2B Overdue Invoice (Liquidity Crunch)*: FMCG invoice 28 days overdue.
  - 💳 *SaaS Subscription Payment Glitch*: Card declined due to bank switch timeout.
  - 📦 *Disputed Retail Goods Delivery*: Invoice contested due to damaged packaging.
  - ⚡ *UPI AutoPay Mandate Expired*: Recurring debit failed due to expired e-mandate.
  - *Or customize custom customer IDs, amounts, and failure descriptions.*
- **Live 3-Step Execution Animation**: Watch the Detective, Strategist, and Guardian agents think and return decisions in real time.
- **Structured Executive Results**: Root cause with quoted reasoning, strategy, compliance status, preview of the AI-drafted email with a **1-click Copy Draft** button, and deep-link to the created case.

### 4. Full Chronological Audit Trails (`/cases/:id`)
- Deep inspection of any case.
- Interactive **Demo Resolution Override**: Allows judges and evaluators to manually test the *"Mark as Kept"* flow without waiting for real bank webhooks.
- Audit timeline explicitly attributes actions to `root_cause_diagnosis_agent`, `intervention_router_agent`, `compliance_gate`, `promise_extraction_agent`, or `manual_demo_override`.

### 5. Fair Debt Compliance Gate (`/compliance`)
- Monitors customer contact frequency and broken promise counts.
- Enforces strict stopping rules:
  - Max 3 contacts within 7 days.
  - Max 1 broken promise before requiring human escalation.
- Intercepts non-compliant outreach into a dedicated **Exceptions Queue** (`/exceptions`).

---

## Agent Taxonomies & Guardrails

### 1. Root-Cause Taxonomy (`ROOT_CAUSES`)
| Root Cause | Description | Default Strategy |
|---|---|---|
| `soft_decline` | Transient technical or switch timeout | **Silent Retry** (background, no customer outreach) |
| `hard_decline_or_expired` | Permanently invalid card or revoked mandate | **Payment Method Update Request** via WhatsApp/Email |
| `dispute` | Contested charges, delivery discrepancy, or billing error | **Dispute Resolution Draft** via Email |
| `cash_flow_distress` | Chronic liquidity crunch (45+ days late, NSF) | **Payment Plan Offer** (2-part installment proposal) |
| `forgetfulness` | Isolated oversight on a clean track record | **Friendly Courteous Nudge** via WhatsApp/SMS |

### 2. Compliance Stopping Rules
- `MAX_CONTACTS_BEFORE_ESCALATION = 3`
- `MAX_BROKEN_PROMISES_BEFORE_ESCALATION = 1`
- When breached, outreach is automatically intercepted as `blocked_pending_review` and flagged for manual intervention.

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2
- **Database**: PostgreSQL 16 (via Docker Compose)
- **ORM & Migrations**: SQLAlchemy 2.0, Alembic
- **LLM Engine**: Groq Cloud API (OpenAI-compatible SDK with structured function calling)
- **Frontend**: React, Vite, Framer Motion, Recharts, React Router DOM, Lucide Icons, Axios
- **Payment Stubs**: Razorpay Python SDK integration

---

## Project Structure

```
revenue-recovery/
├── backend/
│   ├── app/
│   │   ├── main.py                             # FastAPI entry point & CORS configuration
│   │   ├── constants.py                        # Single source of truth: taxonomies & compliance caps
│   │   ├── database.py                         # SQLAlchemy engine & sessionmaker
│   │   ├── models.py                           # 8 relational tables with cascading relationships
│   │   ├── schemas.py                          # Pydantic v2 request/response schemas
│   │   ├── routers/
│   │   │   ├── cases.py                        # /cases, /cases/simulate, /metrics/recovery-summary
│   │   │   ├── events.py                       # /events ingestion endpoints
│   │   │   ├── invoices.py                     # /invoices management
│   │   │   ├── diagnosis.py                    # /diagnose/run batch endpoints
│   │   │   ├── intervention.py                 # /route/run batch intervention endpoints
│   │   │   ├── promises.py                     # /replies/process, /promises/evaluate, /compliance
│   │   │   ├── dispatch.py                     # /dispatch/run, /reconcile endpoints
│   │   │   └── razorpay.py                     # Razorpay webhook stubs
│   │   ├── services/
│   │   │   ├── diagnosis_agent.py              # Root-Cause Detective Agent (Groq tool calling)
│   │   │   ├── intervention_agent.py           # Intervention Strategist & Message Drafter
│   │   │   ├── promise_agent.py                # Promise Extractor (inbound customer reply parser)
│   │   │   ├── promise_evaluator.py            # Promise status & broken promise tracking
│   │   │   ├── compliance_service.py           # Contact frequency caps & escalation engine
│   │   │   ├── context_builder.py              # Telemetry & customer history aggregation
│   │   │   ├── dispatch_service.py             # Multi-channel dispatch & silent retries
│   │   │   ├── reconciliation_service.py       # Recovery settlement verification
│   │   │   └── event_sync.py                   # Sync invoices into unified events table
│   │   └── data/
│   │       ├── generate_synthetic_invoices.py        # 60 realistic FMCG B2B invoices
│   │       ├── generate_synthetic_consumer_events.py  # 30 consumer checkout/sub/mandate events
│   │       └── generate_synthetic_customer_replies.py # Inbound customer responses
│   ├── alembic/                                # Database migration scripts
│   ├── tests/                                  # 35+ pytest automated tests
│   ├── requirements.txt                        # Python dependencies
│   └── .env                                    # Environment configuration (Groq & DB)
├── frontend/
│   ├── src/
│   │   ├── api.js                              # Centralized Axios API client
│   │   ├── components/
│   │   │   ├── Navbar.jsx                      # Navigation header
│   │   │   ├── HonestyBanner.jsx               # Metrics integrity disclosure banner
│   │   │   ├── AgentSimulatorModal.jsx         # Live multi-agent execution modal
│   │   │   ├── AnimatedCounter.jsx             # Smooth numerical ticker
│   │   │   ├── LoadingState.jsx                # Glassmorphic loading view
│   │   │   └── ErrorState.jsx                  # Graceful error state with retry
│   │   ├── pages/
│   │   │   ├── Overview.jsx                    # Executive recovery dashboard & funnel
│   │   │   ├── CaseExplorer.jsx                # Case command center with live search & KPIs
│   │   │   ├── CaseDetail.jsx                  # Unified case view with audit timeline
│   │   │   ├── Exceptions.jsx                  # Broken promises & blocked outreach queue
│   │   │   └── Compliance.jsx                  # Escalated customers & contact monitoring
│   │   ├── index.css                           # Executive slate design system
│   │   ├── motion.js                           # Framer motion transition presets
│   │   ├── App.jsx                             # Router setup
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml                          # PostgreSQL 16 service
└── README.md
```

---

## Quickstart Guide

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- Docker and Docker Compose

### 1. Start Database & Backend

```bash
# 1. Start PostgreSQL 16 container
docker compose up -d

# 2. Activate Python virtual environment
source venv/bin/activate

# 3. Apply database migrations
cd backend
alembic upgrade head

# 4. Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base URL: **`http://localhost:8000`**
- Interactive Swagger Docs: **`http://localhost:8000/docs`**

### 2. Start Frontend Dashboard

In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

- Dashboard UI: **`http://localhost:5174`** (or `http://localhost:5173`)

---

## Simulating & Testing the Agents

### Option A: Via the Frontend UI (Recommended)
1. Open the dashboard at **`http://localhost:5174/cases`**.
2. Click the glowing **`⚡ Ingest & Run Recovery Agent`** button in the header.
3. Select any scenario preset (e.g. *B2B Overdue Invoice* or *SaaS Subscription Payment Glitch*).
4. Click **`Execute Agent Pipeline`**.
5. Watch the agents diagnose the failure, determine the strategy, draft the email/message, and check compliance in real time.
6. Click **`Inspect Full Case & Audit Trail`** to view the newly created record.

### Option B: Via Direct API Call
```bash
curl -s -X POST http://localhost:8000/cases/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "TEST-CUST-LIVE-01",
    "amount": 75000.0,
    "source_type": "invoice",
    "currency": "INR",
    "scenario_title": "B2B Overdue FMCG Invoice",
    "failure_reason": "Invoice 35 days overdue, multiple previous late settlements",
    "days_overdue": 35
  }'
```

### Option C: Batch Pipeline Seeding
To seed fresh synthetic FMCG invoices, consumer events, and run the entire batch pipeline:
```bash
# In backend/ directory:
python -m app.data.generate_synthetic_invoices --reset
python -m app.data.generate_synthetic_consumer_events --reset
curl -X POST http://localhost:8000/sync/invoices-to-events
curl -X POST http://localhost:8000/diagnose/run
curl -X POST http://localhost:8000/route/run
curl -X POST http://localhost:8000/dispatch/run
python -m app.data.generate_synthetic_customer_replies --reset
curl -X POST http://localhost:8000/replies/process
curl -X POST http://localhost:8000/promises/evaluate
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Verifies service and database connectivity |
| `GET` | `/metrics/recovery-summary` | Aggregate recovery rates, root-cause breakdown, exception list, and funnel |
| `GET` | `/cases` | Filterable, paginated case explorer records |
| `GET` | `/events/{id}/case` | Unified case context with complete chronological audit log |
| `POST` | `/cases/simulate` | Ingests a failure, executes diagnosis + intervention agents live, and returns decisions |
| `POST` | `/promises/{id}/mark-kept` | Manual demo override to mark a promise as paid (reconciled) |
| `POST` | `/diagnose/run` | Batch root-cause diagnosis for all undiagnosed events |
| `POST` | `/route/run` | Batch intervention routing and outreach drafting |
| `POST` | `/dispatch/run` | Batch outreach execution and simulated silent retries |
| `POST` | `/replies/process` | Batch promise extraction from inbound customer messages |
| `POST` | `/promises/evaluate` | Evaluates pending promises against current date |
| `GET` | `/compliance` | List of escalated customers breaching contact limits |

---

## Automated Test Suite

All 35+ automated tests verify data consistency, agent routing invariants, prompt function calling, compliance gates, and recovery metric calculations:

```bash
cd backend
pytest -v
```

Frontend production bundle verification:
```bash
cd frontend
npm run build
```

---

## License

MIT License. Built for autonomous revenue recovery and fair debt resolution.