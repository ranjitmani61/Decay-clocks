# Decay Clocks

[![CI](https://github.com/ranjitmani61/Decay-clocks/actions/workflows/ci.yml/badge.svg)](https://github.com/ranjitmani61/Decay-clocks/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Multi‑axis decision reliability governance layer with cost‑informed escalation.**

Decay Clocks wraps every automated decision node (ML model, business rule, API contract, …) with a continuously decaying reliability vector and a mathematically grounded escalation policy.

---

## Why Decay Clocks?

Automated decisions silently decay. A model trained in 2022 approves loans in 2026 based on a world that no longer exists.  
Existing tools detect drift *after* failure. Decay Clocks anticipates it by tracking **five independent reliability axes** – structural, performance, context, regulatory, and temporal – and tells you **"this decision is no longer trustworthy"** *before* something breaks.

---

## Architecture

```
                    ┌───────────────────────────┐
                    │      Signal Ingestion     │   ← regulatory, macro, drift
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   Multi‑Axis Reliability  │   R(t) = (R_s,R_p,R_c,R_r,R_t)
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │  Cost‑Informed Hazard     │   H(t) = Σ w_i(1‑R_i)
                    └─────────────┬─────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │ ACTIVE              │ PROVISIONAL         │ ESCALATE
            │ (healthy)           │ (flag decisions)    │ (human review)
            └─────────────────────┘                     │
                                          ┌────────────▼────────────┐
                                          │  Temporal Workflow      │
                                          │  Human‑review tasks     │
                                          └─────────────────────────┘
```

---

## Quickstart (Docker)

```bash
git clone https://github.com/ranjitmani61/Decay-clocks.git
cd Decay-clocks
docker compose -f docker/compose/docker-compose.yml up -d
docker compose -f docker/compose/docker-compose.yml exec api alembic upgrade head
curl http://localhost:8000/health
```

You can now register nodes, ingest signals, and see governance in action.  
See the [integration demo](scripts/integration_demo.py) for a complete example.

---

## Quickstart (local Python)

```bash
git clone https://github.com/ranjitmani61/Decay-clocks.git
cd Decay-clocks
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
docker compose -f docker/compose/docker-compose.yml up -d postgres redis temporal
alembic upgrade head
uvicorn src.core.api.main:app --reload
```

Then open `http://localhost:8000/docs` for the interactive API.

---

## Key capabilities

- **5‑axis reliability vector** – structural, performance, context, regulatory, temporal.
- **Cost‑informed governance** – escalate only when expected loss > intervention cost.
- **Nonlinear hazard modes** – hard gate, max, quadratic, linear.
- **Monotonic state machine** – risk never auto‑downgrades.
- **Neutral‑time recovery** – stale IN_REVIEW nodes automatically return to ACTIVE after cooldown.
- **Autonomous resilience** – surge‑calm, auto‑suspend, batch review.
- **Temporal human‑review workflows** – durable, observable escalation tasks.
- **Full observability** – Prometheus metrics, structured JSON logs, state‑transition counters.
- **Property‑based tested** – Hypothesis for invariant validation.
- **103 tests** – unit, integration, and property‑based.

---

## Repository structure

```
src/
├── core/
│   ├── api/          # FastAPI REST endpoints
│   ├── engine/       # Reliability dynamics, hazard, calibration
│   ├── models/       # SQLAlchemy ORM (Node, AuditLog, EscalationTask, …)
│   ├── orchestrator/ # Pipeline, escalation, config validation
│   ├── scheduler/    # Batch runner & reconciliation
│   ├── signals/      # Catalogue, bus, feeds
│   └── utils/        # Metrics, logging
├── worker/           # Temporal worker & dispatcher
tests/                # 103 tests (unit + integration + property)
```

For full documentation, see `docs/` directory.
