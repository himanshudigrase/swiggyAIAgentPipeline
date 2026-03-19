# AI Agent Evaluation Pipeline

> Automated evaluation infrastructure for production AI agents — detect regressions, align with human feedback, and auto-generate improvement suggestions.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Evaluation Framework](#evaluation-framework)
- [Self-Update Engine](#self-update-engine)
- [Design Decisions](#design-decisions)
- [Scaling Strategy](#scaling-strategy)
- [Trade-offs](#trade-offs)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Client / AI Agent                      │
└────────────────────────┬─────────────────────────────────┘
                         │ POST /ingest
                         ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Backend (Port 8000)                  │
│  /ingest  /evaluations  /feedback  /suggestions  /meta   │
│              Swagger UI at /docs                          │
└──────┬───────────────────────────────┬───────────────────┘
       │ store                         │ enqueue job
       ▼                               ▼
┌─────────────┐               ┌────────────────────┐
│ PostgreSQL  │               │  Redis (Job Queue) │
│  5 tables   │               │                    │
└─────────────┘               └────────┬───────────┘
       ▲                               │ consume
       │ write results                 ▼
       │                    ┌──────────────────────┐
       └────────────────────│  Celery Worker       │
                            │  ┌────────────────┐  │
                            │  │ Orchestrator   │  │
                            │  ├────────────────┤  │
                            │  │ Heuristic Eval │  │
                            │  │ Tool Call Eval │  │
                            │  │ Coherence Eval │  │
                            │  │ LLM-as-Judge   │  │
                            │  └────────────────┘  │
                            └──────────────────────┘

        ┌────────────────────────────┐
        │  Streamlit Dashboard       │
        │  Port 8501                 │
        │  5 pages → calls API above │
        └────────────────────────────┘
```

### Key Design Principle: Async-First
Ingestion (`POST /ingest`) returns **202 Accepted** immediately. Evaluation jobs run in the background via Celery + Redis. This means ingestion can handle high throughput (1000+ conversations/minute) without LLM latency blocking the HTTP response.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- A free [Google Gemini API key](https://aistudio.google.com/app/apikey) (takes 30 seconds)

### 1. Clone & Configure
```bash
git clone <your-repo>
cd swiggyAssignment

# Copy the env file and add your Gemini key
cp .env.example .env
# Edit .env and set: GEMINI_API_KEY=your-key-here
```

### 2. Start All Services
```bash
docker-compose up --build
```

This starts:
| Service | URL | Description |
|---|---|---|
| FastAPI API | http://localhost:8000 | REST API |
| Swagger UI | http://localhost:8000/docs | Interactive API docs |
| Streamlit UI | http://localhost:8501 | Dashboard |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Job queue |
| Celery Worker | — | Background evaluation jobs |

### 3. Test It
```bash
# Health check
curl http://localhost:8000/health

# Ingest a conversation (uses the assignment sample schema)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_test_001",
    "agent_version": "v2.3.1",
    "turns": [
      {"turn_id": 1, "role": "user", "content": "Book a flight to NYC next week"},
      {"turn_id": 2, "role": "assistant", "content": "I will help you book that flight.",
       "tool_calls": [{"tool_name": "flight_search", "parameters": {"destination": "NYC", "date_range": "2024-01-22/2024-01-28"}, "result": {"status": "success"}, "latency_ms": 450}]}
    ],
    "metadata": {"total_latency_ms": 1200, "mission_completed": true}
  }'

# Check evaluation result (wait ~3 seconds for async evaluation)
curl http://localhost:8000/evaluations/conv_test_001

# Generate improvement suggestions
curl -X POST http://localhost:8000/suggestions/generate -H "Content-Type: application/json" -d '{"window": 100}'
```

### No LLM Key? Use Mock Mode
```bash
# In .env, set:
LLM_MOCK_MODE=true
```
The system returns realistic mock scores — all features work without a real API key.

---

## API Documentation

Full interactive docs at **http://localhost:8000/docs**.

### Ingestion
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest single conversation (202 Accepted) |
| `POST` | `/ingest/batch` | Ingest up to 500 conversations |

### Evaluations
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/evaluations` | Paginated list, filterable by `agent_version` |
| `GET` | `/evaluations/{conversation_id}` | Single evaluation result |

### Feedback
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/feedback/annotate` | Submit human annotation |
| `GET` | `/feedback/{conversation_id}` | Inter-annotator agreement report |

### Suggestions
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/suggestions` | List improvement suggestions |
| `POST` | `/suggestions/generate` | Trigger suggestion generation |

### Meta-Evaluation
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/meta/calibration` | LLM vs. human agreement metrics |
| `GET` | `/meta/coverage` | Failure category distribution |

---

## Evaluation Framework

Four evaluators run in parallel on every conversation:

### 1. Heuristic Evaluator (10% weight)
Pure Python, no LLM. Instant.
- ⏱️ Latency threshold check (configurable, default 1000ms)
- 📋 Required field presence (role, content per turn)
- 🔧 Tool execution status check
- ✅ Mission completion flag

### 2. Tool Call Evaluator (35% weight)
Logic-based analysis of tool usage.
- **Selection accuracy**: Did the agent call a tool relevant to the user's intent?
- **Parameter accuracy**: Are required parameters present and non-null?
- **Hallucination detection**: Are parameter values grounded in the conversation?
- **Execution success**: Did the tool return `status: success`?

### 3. Multi-turn Coherence Evaluator (20% weight)
LLM-assisted. Skipped for conversations ≤ 2 turns.
- Context maintenance: Are user preferences from early turns respected?
- Contradiction detection: Does the agent contradict itself across turns?
- Reference resolution: Are pronouns and references resolved correctly?

### 4. LLM-as-Judge Evaluator (35% weight)
Structured LLM prompt → JSON output.
- Response quality (0.0–1.0): Coherence, completeness
- Helpfulness (0.0–1.0): Does the response move the user toward their goal?
- Factuality (0.0–1.0): Are stated facts plausibly correct?

### LLM Provider
- **Default**: Google Gemini `gemini-1.5-flash` (free tier, 1500 req/day)
- **Override**: Set `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- **Mock**: Set `LLM_MOCK_MODE=true` — no key needed

---

## Self-Update Engine

The key differentiator: the pipeline improves itself.

### How It Works

```
Recent Evaluations
       ↓
Pattern Detector (scans last N=100 evals)
   - Groups issues by type
   - Calculates failure rates
   - Classifies severity (high/medium/low)
       ↓
┌──────────────────────────┐
│  Prompt Suggester (LLM)  │ → Specific prompt changes with rationale
│  Tool Suggester (LLM)    │ → Parameter description improvements
└──────────────────────────┘
       ↓
Stored in suggestions table
       ↓
GET /suggestions → Dashboard
```

### Sample Scenario: Tool Regression
```
1. 20% of recent evals show "empty_parameter" for flight_search.date_range
2. Pattern detector flags: severity=HIGH, failure_rate=0.20
3. Prompt suggester generates:
   "Add explicit instruction: 'Always extract dates in ISO 8601 format (YYYY-MM-DD).
   If the user says next week, calculate the exact date range.'"
4. Available via GET /suggestions for the team to review
```

### Meta-Evaluation (Flywheel)
```
Human Annotation
       ↓
Compare with LLM-as-Judge score
       ↓
Store in evaluator_calibration table
       ↓
GET /meta/calibration → agreement %, avg delta
       ↓
Low agreement → evaluator prompt needs updating
```

---

## Design Decisions

### Why Async Evaluation?
LLM inference takes 2–10 seconds. Blocking ingestion on evaluation would cap throughput at ~6 conversations/second. With async Celery workers, ingestion is I/O bound (DB write + Redis enqueue) — easily 1000+ conversations/minute.

### Why PostgreSQL + JSONB?
Conversation data is hierarchical (turns → tool_calls → results). JSONB lets us store this flexibly while still being queryable. Avoids complex join schemas for data we often read as a whole unit.

### Why Gemini Free Tier?
For a take-home demo, reviewer friction is UX. A free key means the reviewer runs `docker-compose up` and everything works. OpenAI requires billing setup and costs money — bad UX for evaluation.

### Why Modular Evaluators?
Each evaluator is isolated behind a common `BaseEvaluator` interface. Adding a new evaluator (e.g., a grammar checker) requires writing one class and registering it in the orchestrator. No changes to routing, storage, or any other layer.

---

## Scaling Strategy

| Scale | Bottleneck | Solution |
|---|---|---|
| **10x (10k/min)** | Celery worker concurrency | Add more worker replicas (`--concurrency=8`, horizontal scale) |
| **10x** | PostgreSQL write throughput | Add read replicas, connection pooling (PgBouncer) |
| **100x (100k/min)** | LLM API rate limits | Sample LLM evals (10% of traffic); run heuristic+tool evals on all |
| **100x** | Redis as broker | Migrate to Kafka for durability + replay capability |
| **100x** | DB storage | Partition by `agent_version` + archive old evals to S3/cold storage |
| **Production** | Cost | Cache LLM responses for identical conversations; batch LLM calls |

### Sampling Strategy (Production)
```
All conversations:    Heuristic + Tool Call Evaluator (100%)
Random 10% sample:   LLM-as-Judge + Coherence Evaluator
Human annotated:     Full evaluation + calibration comparison
```

---

## Trade-offs

| Decision | Optimized For | What We Sacrificed |
|---|---|---|
| Async evaluation | Ingestion throughput | Immediate evaluation results |
| Gemini free tier | Reviewer experience | Slightly lower eval quality vs. GPT-4 |
| Modular evaluators | Extensibility | Small overhead per evaluation |
| PostgreSQL JSONB | Flexibility | Less structure than a fully normalized schema |
| Rule-based tool eval | Speed + reliability | Misses semantic-level tool misuse |
| Mock mode | Developer experience | Realistic baseline scores |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini API key (primary LLM) |
| `OPENAI_API_KEY` | — | OpenAI API key (optional override) |
| `LLM_PROVIDER` | `gemini` | `"gemini"` or `"openai"` |
| `LLM_MOCK_MODE` | `false` | Skip LLM calls, return mock scores |
| `LATENCY_THRESHOLD_MS` | `1000` | Latency warning threshold |
| `PATTERN_SCAN_WINDOW` | `100` | How many evals to scan for patterns |
| `AUTO_LABEL_CONFIDENCE_THRESHOLD` | `0.8` | Below this = route to human review |
| `ANNOTATOR_AGREEMENT_THRESHOLD` | `0.6` | Below this = flag as disagreement |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | — | Redis connection string |
