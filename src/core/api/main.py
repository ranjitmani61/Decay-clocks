from __future__ import annotations
import uuid, json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from prometheus_client import generate_latest

from src.core.models.node import Node, NodeClass, Criticality, CostConfig
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.api.database import get_db
from src.core.api.config_loader import get_active_cost_config, get_cost_config_for_node
from src.core.api.catalogue import get_catalogue
from src.core.signals.bus import DEFAULT_DEBOUNCE_HOURS as DEBOUNCE
from src.core.utils.metrics import REQUEST_COUNT, PIPELINE_RUNS
from src.core.utils.logging import setup_logging
from src.core.output.wrapper import wrap_decision

def _ensure_datetime(ts):
    """Convert an ISO‑8601 timestamp string to a timezone‑aware datetime."""
    if isinstance(ts, datetime):
        return ts
    try:
        # handle 'Z' suffix
        s = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)

setup_logging()

app = FastAPI(title="Decay Clocks API", version="1.0.0")

class NodeCreate(BaseModel):
    node_class: str
    version_ref: str
    owner_team: str
    criticality: str
    domain_tags: list[str] = []
    decay_alpha: float = 0.01
    environment: str = "production"
    cost_config_id: Optional[str] = None

class SignalIngest(BaseModel):
    raw_events: list[dict]

class WrapRequest(BaseModel):
    node_id: str
    original_output: Dict[str, Any]

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
    start = time.time()
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

    # Resolve cost_config_id
    config_id = None
    if node_in.cost_config_id:
        try:
            config_uuid = uuid.UUID(node_in.cost_config_id)
            row = db.get(CostConfig, config_uuid)
            if not row:
                raise HTTPException(status_code=400, detail="cost_config_id not found")
            config_id = config_uuid
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cost_config_id")
    else:
        active_row = db.query(CostConfig).filter(CostConfig.active == True).first()
        config_id = active_row.id if active_row else None

    node = Node(
        node_class=node_class,
        version_ref=node_in.version_ref,
        owner_team=node_in.owner_team,
        criticality=criticality,
        domain_tags=node_in.domain_tags,
        decay_alpha=node_in.decay_alpha,
        environment=node_in.environment,
        cost_config_id=config_id,
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

    return {
        "weights": row.weights,
        "C_err": row.C_err,
        "C_int": row.C_int,
        "provisional_hazard": row.provisional_hazard,
        "floor_axes": row.floor_axes,
        "hazard_mode": row.hazard_mode if getattr(row, "hazard_mode", None) else "linear",
        "dominant_axes": row.dominant_axes if isinstance(row.dominant_axes, list) else (json.loads(row.dominant_axes) if isinstance(row.dominant_axes, str) else []),
    }

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

    for node in nodes:
        node_cost_config = get_cost_config_for_node(node, db)
        process_node_lifecycle(
            node_id=node.node_id,
            db=db,
            catalogue=catalogue,
            raw_events=[{**ev, "timestamp": _ensure_datetime(ev.get("timestamp"))} for ev in payload.raw_events],
            now=now,
            debounce_config=DEBOUNCE,
            cost_config=node_cost_config,
        )
        PIPELINE_RUNS.inc()
        updated.append(str(node.node_id))
    return {"updated_nodes": updated}

@app.post("/decisions/wrap")
def wrap_endpoint(req: WrapRequest, db: Session = Depends(get_db)):
    try:
        nid = uuid.UUID(req.node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node_id")
    try:
        wrapped = wrap_decision(node_id=nid, original_output=req.original_output, db=db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return wrapped

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

class CostConfigSet(BaseModel):
    """Request body for updating the active cost configuration."""
    weights: Dict[str, float]
    C_err: float
    C_int: float
    provisional_hazard: float
    hazard_mode: str = "linear"
    dominant_axes: list = []
    floor_axes: Dict[str, float]
    environment: str = "production"
    cost_config_id: Optional[str] = None

@app.post("/config/cost")
def set_cost_config(config: CostConfigSet, db: Session = Depends(get_db)):
    """Replace the currently active cost configuration.
    
    The new configuration becomes effective for all subsequent signal
    ingestions and decision wraps.
    """
    # Deactivate any existing active config
    db.query(CostConfig).update({"active": False})
    # Create the new active config
    new_cfg = CostConfig(
        active=True,
        weights=config.weights,
        C_err=config.C_err,
        C_int=config.C_int,
        provisional_hazard=config.provisional_hazard,
        floor_axes=config.floor_axes,
        hazard_mode=config.hazard_mode,
        dominant_axes=config.dominant_axes if hasattr(config, 'dominant_axes') else [],
        environment=config.environment,
    )
    db.add(new_cfg)
    db.commit()
    return {"message": "Cost config updated", "id": str(new_cfg.id)}

class AdminReset(BaseModel):
    confirm: bool = True

@app.post("/admin/reset")
def admin_reset(db: Session = Depends(get_db)):
    """Delete all nodes and dependent records in the correct order."""
    from src.core.models.node import EscalationTask, AuditLog, DependencyEdge, Node
    # Only delete demo data
    demo_nodes = db.query(Node.node_id).filter(Node.environment == "demo").subquery()
    db.query(EscalationTask).filter(EscalationTask.node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(AuditLog).filter(AuditLog.node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(DependencyEdge).filter(DependencyEdge.parent_node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(Node).filter(Node.environment == "demo").delete()
    db.query(CostConfig).filter(CostConfig.environment == "demo").delete()
    db.commit()
    return {"status": "ok", "message": "All demo data cleared. Production data untouched."}

@app.get("/health")
def health():
    return {"status": "ok"}
