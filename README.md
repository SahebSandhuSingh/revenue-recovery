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
│   │   ├── main.py                             # FastAPI entry point, CORS & /health
│   │   ├── constants.py                        # Single source of truth: ROOT_CAUSES taxonomy
│   │   ├── database.py                         # Engine, sessionmaker, Base, get_db
│   │   ├── models.py                           # SQLAlchemy 2.0 ORM models (7 tables)
│   │   ├── schemas.py                          # Pydantic v2 validation & response schemas
│   │   ├── routers/
│   │   │   ├── events.py                       # GET /events, POST /events
│   │   │   ├── invoices.py                     # GET /invoices, POST /invoices
│   │   │   └── diagnosis.py                    # POST /sync/invoices-to-events, POST /diagnose/run, GET /diagnoses
│   │   ├── services/
│   │   │   ├── context_builder.py              # Case context & customer history aggregation
│   │   │   ├── diagnosis_agent.py              # GPT-4o root-cause diagnosis agent & batch runner
│   │   │   ├── event_sync.py                   # Invoice-to-event synchronization service
│   │   │   └── razorpay_client.py              # Razorpay client wrapper & test stubs
│   │   └── data/
│   │       ├── generate_synthetic_invoices.py        # 60 FMCG B2B invoice generator
│   │       └── generate_synthetic_consumer_events.py  # 30 consumer checkout/sub/mandate events
│   ├── alembic/
│   │   ├── env.py                              # Alembic migration environment (.env aware)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py          # Initial schema migration (7 tables)
│   ├── alembic.ini                             # Alembic configuration
│   ├── requirements.txt                        # Python package dependencies
│   └── .env.example                            # Environment variables template
├── docker-compose.yml                          # PostgreSQL 16 container definition
├── .gitignore
└── README.md
```

---

## Root-Cause Taxonomy

Recoup classifies all revenue-at-risk events into 5 root-cause categories defined in `app/constants.py`:

| Root Cause | Description | Example Evidence |
| :--- | :--- | :--- |
| `soft_decline` | Retryable technical/network glitch | Gateway timeout, bank switch down, temporary NPCI throttle |
| `hard_decline_or_expired` | Permanently invalid payment method | Expired card, revoked UPI mandate, frozen account |
| `dispute` | Retailer/customer contesting charge | Damaged goods, pricing dispute, delivery mismatch |
| `cash_flow_distress` | Chronic liquidity hardship | Non-sufficient funds (NSF), 45+ days overdue, repeated defaults |
| `forgetfulness` | Isolated oversight with clean track record | First offense, >=90% on-time payment track record |

---

## Setup and Quickstart

### 1. Start PostgreSQL with Docker Compose

From the project root:

```bash
docker compose up -d
```

### 2. Set Up Python Virtual Environment

From the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

Create `.env` inside `backend/`:

```bash
cp backend/.env.example backend/.env
```

Set your OpenAI API Key in `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg2://recoup:recoup_dev@127.0.0.1:5432/recoup
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

> [!WARNING]
> **Mock Mode Notice**: If `OPENAI_API_KEY` is not provided or left blank, the diagnosis agent runs in **Mock Fallback Mode**. In mock mode, diagnoses are generated deterministically, reasoning is prefixed with `[MOCK]`, confidence is set to `0.0`, and console warnings will alert you. Before final evaluation runs, ensure a valid `OPENAI_API_KEY` is set.

### 4. Run Database Migrations

Navigate into `backend/` and execute Alembic migrations:

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

Start the API server:

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

---

## Example Usage

**1. Sync Overdue / Disputed Invoices to Events**:
```bash
curl -X POST http://localhost:8000/sync/invoices-to-events
```

**2. Run Batch Diagnosis with GPT-4o**:
```bash
curl -X POST http://localhost:8000/diagnose/run
```

**3. Query Filtered Diagnoses by Root Cause**:
```bash
curl "http://localhost:8000/diagnoses?root_cause=cash_flow_distress"
```