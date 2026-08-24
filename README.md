# Recoup — Root-Cause Revenue Recovery Agent

**Recoup** is an intelligent revenue recovery agent designed to diagnose and resolve payment failures across B2B invoice cycles and consumer recurring billing (checkout, subscriptions, UPI AutoPay / e-mandates).

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI
- **Database**: PostgreSQL 16 (via Docker Compose)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **LLM Agent**: OpenAI SDK (`gpt-4o` with Function/Tool-Calling)
- **Validation**: Pydantic v2
- **Integration Stubs**: Razorpay Python SDK

---

## Directory Structure

```
recoup/
├── backend/
│   ├── app/
│   │   ├── main.py                             # FastAPI entry point & CORS
│   │   ├── constants.py                        # Single source of truth: ROOT_CAUSES & ACTION_TYPES
│   │   ├── database.py                         # Engine, sessionmaker, Base, get_db
│   │   ├── models.py                           # SQLAlchemy 2.0 ORM models (7 tables)
│   │   ├── schemas.py                          # Pydantic v2 validation & response schemas
│   │   ├── routers/
│   │   │   ├── events.py                       # GET /events, POST /events
│   │   │   ├── invoices.py                     # GET /invoices, POST /invoices
│   │   │   ├── diagnosis.py                    # POST /sync/invoices-to-events, POST /diagnose/run, GET /diagnoses
│   │   │   └── intervention.py                 # POST /route/run, GET /actions, GET /events/{id}/action
│   │   ├── services/
│   │   │   ├── context_builder.py              # Case context & customer history aggregation
│   │   │   ├── diagnosis_agent.py              # GPT-4o root-cause diagnosis agent
│   │   │   ├── intervention_agent.py           # GPT-4o intervention router agent
│   │   │   ├── event_sync.py                   # Invoice-to-event synchronization service
│   │   │   └── razorpay_client.py              # Razorpay client wrapper & test stubs
│   │   └── data/
│   │       ├── generate_synthetic_invoices.py        # 60 FMCG B2B invoice generator
│   │       └── generate_synthetic_consumer_events.py  # 30 consumer checkout/sub/mandate events
│   ├── alembic/
│   │   ├── env.py                              # Alembic migration environment (.env aware)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 0001_initial_schema.py          # Initial schema migration (7 tables)
│   │       └── 0002_extend_actions_table.py    # Actions table schema extension
│   ├── alembic.ini                             # Alembic configuration
│   ├── requirements.txt                        # Python package dependencies
│   └── .env.example                            # Environment variables template
├── docker-compose.yml                          # PostgreSQL 16 container definition
├── .gitignore
└── README.md
```

---

## Agent Taxonomies

### 1. Root-Cause Taxonomy (`ROOT_CAUSES`)
- `soft_decline`: Transient technical/network glitch (gateway timeout, bank switch down).
- `hard_decline_or_expired`: Permanently invalid payment method (expired card, revoked mandate).
- `dispute`: Retailer/customer contesting charge or invoice.
- `cash_flow_distress`: Chronic liquidity hardship (NSF, 45+ days overdue, repeated defaults).
- `forgetfulness`: Isolated oversight with clean track record.

### 2. Action Taxonomy (`ACTION_TYPES`)
- `silent_retry`: Background technical retry without customer outreach (Channel: `none`, empty message draft).
- `payment_method_update_request`: Customer notification to update payment instrument (Channels: `email`, `whatsapp`).
- `dispute_resolution_draft`: Tailored response addressing disputed invoices/charges (Channel: `email`).
- `payment_plan_offer`: Flexible installment/deferred payment offer for liquidity distress (Channels: `whatsapp`, `email`).
- `friendly_nudge`: Courteous reminder for clean-history accounts (Channels: `whatsapp`, `sms`).

---

## Setup and Quickstart

### 1. Start PostgreSQL with Docker Compose

```bash
docker compose up -d
```

### 2. Set Up Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

```bash
cp backend/.env.example backend/.env
```

```env
DATABASE_URL=postgresql+psycopg2://recoup:recoup_dev@127.0.0.1:5432/recoup
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

> [!WARNING]
> **Mock Mode Notice**: If `OPENAI_API_KEY` is not provided or left blank, the agent runs in **Mock Fallback Mode**. Reasoning is prefixed with `[MOCK]`, confidence is set to `0.0`, priority defaults to `low`, and console warnings alert you. Set `require_real_agent=true` to enforce strict failure when API keys are missing.

### 4. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### 5. Seed Synthetic Data

```bash
# Seed 60 FMCG B2B Invoices
python -m app.data.generate_synthetic_invoices --reset

# Seed 30 Consumer Payment Failure Events
python -m app.data.generate_synthetic_consumer_events --reset
```

### 6. Run the FastAPI Application Server

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check + active DB `SELECT 1` ping |
| `GET` | `/events` | List events (paginated with `limit`, `offset`) |
| `POST` | `/events` | Create a new event |
| `GET` | `/invoices` | List invoices (paginated, supports `?status=` filter) |
| `POST` | `/invoices` | Create a new invoice |
| `POST` | `/sync/invoices-to-events` | Sync overdue and disputed invoices to events |
| `POST` | `/diagnose/run` | Execute batch root-cause diagnosis for all undiagnosed events |
| `GET` | `/diagnoses` | List diagnoses (paginated, supports `?root_cause=` filter) |
| `GET` | `/events/{event_id}/diagnosis` | Retrieve diagnosis for a specific event |
| `POST` | `/route/run` | Execute batch intervention router for diagnosed events |
| `GET` | `/actions` | List planned actions (paginated, supports `?action_type=` & `?channel=` filters) |
| `GET` | `/events/{event_id}/action` | Retrieve planned action for a specific event |

---

## Example Usage

**1. Sync & Diagnose**:
```bash
curl -X POST http://localhost:8000/sync/invoices-to-events
curl -X POST http://localhost:8000/diagnose/run
```

**2. Route Interventions**:
```bash
curl -X POST http://localhost:8000/route/run
```

**3. Query Planned Actions by Action Type**:
```bash
curl "http://localhost:8000/actions?action_type=payment_plan_offer"
```