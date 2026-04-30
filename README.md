# Decay Clocks

[![CI](https://github.com/ranjitmani61/Decay-clocks/actions/workflows/ci.yml/badge.svg)](https://github.com/ranjitmani61/Decay-clocks/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Multi‑axis decision reliability governance layer with cost‑informed escalation.**  
Decay Clocks wraps every automated decision node (ML model, business rule, API contract, …) with a continuously decaying reliability vector and a mathematically grounded escalation policy.

---

## Why Decay Clocks?
Automated decisions silently decay. A model trained in 2022 approves loans in 2026 based on a world that no longer exists.  
Existing tools detect drift *after* failure. Decay Clocks anticipates it by tracking **five independent reliability axes** – structural, performance, context, regulatory, and temporal – and tells you **“this decision is no longer trustworthy”** *before* something breaks.

---

## Architecture

┌───────────────────────────┐
│ Signal Ingestion │ ← regulatory, macro, drift
└─────────────┬─────────────┘
│
┌─────────────▼─────────────┐
│ Multi‑Axis Reliability │ R(t) = (R_s,R_p,R_c,R_r,R_t)
└─────────────┬─────────────┘
│
┌─────────────▼─────────────┐
│ Cost‑Informed Hazard │ H(t) = Σ w_i(1‑R_i)
└─────────────┬─────────────┘
│
┌─────────────────────┼─────────────────────┐
│ ACTIVE │ PROVISIONAL │ ESCALATE
│ (healthy) │ (flag decisions) │ (human review)
└─────────────────────┘ │
┌────────────▼────────────┐
│ Temporal Workflow │
│ Human‑review tasks │
└─────────────────────────┘


---

## Quickstart

### 1. Clone & start the Docker stack
```bash
git clone https://github.com/ranjitmani61/Decay-clocks.git && cd Decay-clocks
docker compose -f docker/compose/docker-compose.yml up -d
docker compose -f docker/compose/docker-compose.yml exec api alembic upgrade head
