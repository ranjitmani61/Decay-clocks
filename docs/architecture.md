# Decay Clocks – System Architecture

## Overview
Decay Clocks is a **multi‑axis decision reliability governance layer**. It wraps every automated decision node (ML model, business rule, API contract, etc.) with a continuously decaying reliability vector and a cost‑informed escalation policy.

## Core Concepts
- **Decision Node**: any production artefact that produces decisions.
- **Reliability Vector R(t) = (R_s, R_p, R_c, R_r, R_t)**: structural validity, empirical performance, context alignment, regulatory compliance, temporal freshness.
- **Hazard Score H(t)**: a weighted, cost‑aware scalar derived from R(t) that drives governance actions.
- **Governance Actions**: ACTIVE, PROVISIONAL, ESCALATE.

## Key Design Decisions (see ADRs for details)
1. **Multi‑axis instead of a single confidence score** – prevents fragile scalar collapse.
2. **Cost‑informed escalation** – decisions are based on expected loss vs. intervention cost, not arbitrary thresholds.
3. **Immutable audit ledger** – every state change and signal is recorded for compliance.
4. **Temporal workflows** – human review tasks are dispatched via Temporal for durable, observable execution.

## Component Diagram
- **Decision Node Registry (DNR)** – PostgreSQL table holding node metadata and R(t).
- **Signal Ingestion & Bus** – debounces raw external/internal signals and routes them to relevant nodes.
- **Reliability Dynamics Engine** – pure functions that update each axis independently.
- **Hazard Function** – computes governance action from R(t) and cost parameters.
- **Output Wrapper** – annotates every decision with provenance (node_id, confidence, provisional flag).
- **Escalation Dispatcher** – creates Temporal workflows for human review.
- **Scheduler** – periodic batch process that advances all nodes’ reliability clocks.
- **FastAPI REST API** – create nodes, ingest signals, query decisions.
- **Prometheus Metrics & Structured Logging** – observability.

## Data Flow
1. External signals (regulatory changes, macro indices) and internal signals (drift metrics) enter the Signal Bus.
2. The Signal Bus debounces and forwards them to affected nodes.
3. The Reliability Dynamics Engine updates each node’s R(t) using pure mathematical functions.
4. The Hazard Function computes a governance action based on the new R(t) and cost policy.
5. If the action is `PROVISIONAL` or `ESCALATE`, the Output Wrapper marks all future decisions accordingly and the Escalation Dispatcher may create a human review task.
6. All changes are logged to the Audit Ledger.

## Production Readiness
- CI/CD via GitHub Actions (lint, type check, unit/integration tests).
- Prometheus metrics on API requests and pipeline runs.
- Structured JSON logging.
- DB performance indexes (GIN on domain_tags, B‑tree on status/FKs).
- Locust load‑test scripts.

## Remaining (future)
- Admin dashboard.
- Persistent signal catalogue (DB‑backed).
- Advanced calibration learning (Bayesian updates).
