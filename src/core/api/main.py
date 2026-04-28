from __future__ import annotations
import uuid
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from prometheus_client import generate_latest

from src.core.models.node import Node, NodeClass, Criticality
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.api.database import get_db
from src.core.api.catalogue import get_catalogue
from src.core.signals.bus import DEFAULT_DEBOUNCE_HOURS as DEBOUNCE
from src.core.utils.metrics import REQUEST_COUNT, PIPELINE_RUNS
from src.core.utils.logging import setup_logging

# Initialise structured logging
setup_logging()

app = FastAPI(title="Decay Clocks API", version="1.0.0")


class NodeCreate(BaseModel):
    node_class: str
    version_ref: str
    owner_team: str
    criticality: str
    domain_tags: list[str] = []
    decay_alpha: float = 0.01


class SignalIngest(BaseModel):
    raw_events: list[dict]


def serialize_node(node: Node) -> dict:
    return {
        "node_id": str(node.node_id),
        "node_class": node.node_class.value,
        "version_ref": node.version_ref,
        "owner_team": node.owner_team,
        "criticality": node.criticality.value,
        "domain_tags": node.domain_tags,
        "reliability": {
            "r_s": node.r_s,
            "r_p": node.r_p,
            "r_c": node.r_c,
            "r_r": node.r_r,
            "r_t": node.r_t,
        },
        "status": node.status.value,
        "decay_alpha": node.decay_alpha,
        "last_validation_time": node.last_validation_time.isoformat()
        if node.last_validation_time else None,
        "registration_time": node.registration_time.isoformat()
        if node.registration_time else None,
    }


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    time.time()
    response = await call_next(request)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    return response


@app.post("/nodes", status_code=201)
def create_node(node_in: NodeCreate, db: Session = Depends(get_db)):
    try:
        node_class = NodeClass(node_in.node_class)
        criticality = Criticality(node_in.criticality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    node = Node(
        node_class=node_class,
        version_ref=node_in.version_ref,
        owner_team=node_in.owner_team,
        criticality=criticality,
        domain_tags=node_in.domain_tags,
        decay_alpha=node_in.decay_alpha,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return serialize_node(node)


@app.get("/nodes/{node_id}")
def get_node(node_id: uuid.UUID, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return serialize_node(node)


@app.post("/signals/ingest")
def ingest_signals(payload: SignalIngest,
                   db: Session = Depends(get_db),
                   catalogue: dict = Depends(get_catalogue)):
    updated = []
    now = datetime.now(timezone.utc)
    all_tags = set()
    for ev in payload.raw_events:
        all_tags.update(ev.get("domain_tags", []))
    if not all_tags:
        return {"updated_nodes": []}

    conditions = [Node.domain_tags.any(tag) for tag in all_tags]
    nodes = db.query(Node).filter(or_(*conditions)).all()

    cost_config = {
        "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
        "C_err": 500.0,
        "C_int": 1000.0,
        "provisional_hazard": 0.2,
        "floor_axes": {"r": 0.2, "s": 0.1},
    }
    for node in nodes:
        process_node_lifecycle(
            node_id=node.node_id,
            db=db,
            catalogue=catalogue,
            raw_events=payload.raw_events,
            now=now,
            debounce_config=DEBOUNCE,
            cost_config=cost_config,
        )
        PIPELINE_RUNS.inc()
        updated.append(str(node.node_id))
    return {"updated_nodes": updated}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health")
def health():
    return {"status": "ok"}
