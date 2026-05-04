from __future__ import annotations
import uuid, json, time, os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from prometheus_client import generate_latest

from src.core.models.node import Node, NodeClass, Criticality, NodeStatus, CostConfig, EscalationTask, AuditLog
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.api.database import get_db
from src.core.api.catalogue import get_catalogue
from src.core.api.config_loader import get_active_cost_config, get_cost_config_for_node
from src.core.signals.bus import DEFAULT_DEBOUNCE_HOURS as DEBOUNCE
from src.core.utils.metrics import REQUEST_COUNT, PIPELINE_RUNS
from src.core.utils.logging import setup_logging
from src.core.output.wrapper import wrap_decision

# ── App setup ──────────────────────────────────────────────
setup_logging()
app = FastAPI(title="Decay Clocks API", version="1.0.0")
app.mount("/static", StaticFiles(directory="src/core/api/static"), name="static")

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


# ── Helpers ────────────────────────────────────────────────
def _ensure_datetime(ts):
    """Convert an ISO‑8601 timestamp string to a timezone‑aware datetime."""
    if isinstance(ts, datetime):
        return ts
    try:
        s = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def serialize_node(node: Node) -> dict:
    return {
        "node_id": str(node.node_id),
        "node_class": node.node_class.value,
        "version_ref": node.version_ref,
        "owner_team": node.owner_team,
        "criticality": node.criticality.value,
        "domain_tags": node.domain_tags,
        "reliability": {
            "r_s": node.r_s, "r_p": node.r_p, "r_c": node.r_c, "r_r": node.r_r, "r_t": node.r_t,
        },
        "status": node.status.value,
        "decay_alpha": node.decay_alpha,
        "last_validation_time": node.last_validation_time.isoformat() if node.last_validation_time else None,
        "registration_time": node.registration_time.isoformat() if node.registration_time else None,
    }


# ── Middleware ─────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    return response


# ── Pydantic Models ───────────────────────────────────────
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

class CostConfigSet(BaseModel):
    weights: Dict[str, float]
    C_err: float
    C_int: float
    provisional_hazard: float
    floor_axes: Dict[str, float]
    hazard_mode: str = "linear"
    dominant_axes: list = []
    environment: str = "production"

class AdminResolveRequest(BaseModel):
    note: str = "Resolved via dashboard"

class AdminRecertifyRequest(BaseModel):
    note: str = "Recertified via dashboard"


# ── Dashboard ─────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    with open("src/core/api/static/dashboard.html", "r") as f:
        return HTMLResponse(content=f.read())


# ── Core Endpoints ────────────────────────────────────────
@app.post("/nodes", status_code=201)
def create_node(node_in: NodeCreate, db: Session = Depends(get_db)):
    try:
        node_class = NodeClass(node_in.node_class)
        criticality = Criticality(node_in.criticality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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


@app.get("/nodes")
def list_nodes(db: Session = Depends(get_db), limit: int = 50):
    nodes = db.query(Node).order_by(Node.registration_time.desc()).limit(limit).all()
    return [serialize_node(n) for n in nodes]


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
        cost_config = get_cost_config_for_node(node, db)
        process_node_lifecycle(
            node_id=node.node_id,
            db=db,
            catalogue=catalogue,
            raw_events=[{**ev, "timestamp": _ensure_datetime(ev.get("timestamp"))} for ev in payload.raw_events],
            now=now,
            debounce_config=DEBOUNCE,
            cost_config=cost_config,
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


@app.post("/config/cost")
def set_cost_config(config: CostConfigSet, db: Session = Depends(get_db)):
    db.query(CostConfig).update({"active": False})
    new_cfg = CostConfig(
        active=True,
        weights=config.weights,
        C_err=config.C_err,
        C_int=config.C_int,
        provisional_hazard=config.provisional_hazard,
        floor_axes=config.floor_axes,
        hazard_mode=config.hazard_mode,
        dominant_axes=config.dominant_axes,
        environment=config.environment,
    )
    db.add(new_cfg)
    db.commit()
    return {"message": "Cost config updated", "id": str(new_cfg.id)}


# ── Admin Endpoints (DEMO_MODE gated) ─────────────────────
@app.post("/admin/escalation/{task_id}/resolve")
def admin_resolve_task(
    task_id: uuid.UUID,
    req: AdminResolveRequest,
    db: Session = Depends(get_db),
):
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Disabled in production")
    task = db.get(EscalationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Task must be IN_PROGRESS")
    task.status = "COMPLETED"
    task.notes = f"{task.notes}\nResolved: {req.note}"
    node = db.get(Node, task.node_id)
    if node:
        remaining = db.query(EscalationTask).filter(
            EscalationTask.node_id == node.node_id,
            EscalationTask.status.in_(["PENDING", "IN_PROGRESS"]),
        ).count()
        if remaining == 0 and node.status == NodeStatus.IN_REVIEW:
            node.status = NodeStatus.ACTIVE
            node.status_changed_at = datetime.now(timezone.utc)
    db.add(AuditLog(node_id=task.node_id, event_type="task_resolved",
                    event_payload={"task_id": str(task.id), "note": req.note}))
    db.commit()
    return {"status": "ok", "message": "Task resolved"}


@app.post("/admin/nodes/{node_id}/recertify")
def admin_recertify_node(
    node_id: uuid.UUID,
    req: AdminRecertifyRequest,
    db: Session = Depends(get_db),
):
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Disabled in production")
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    old_status = node.status.value
    node.status = NodeStatus.ACTIVE
    node.status_changed_at = datetime.now(timezone.utc)
    node.r_s = node.r_p = node.r_c = node.r_r = node.r_t = 1.0
    node.last_validation_time = datetime.now(timezone.utc)
    db.add(AuditLog(node_id=node_id, event_type="node_recertified",
                    event_payload={"old_status": old_status, "note": req.note}))
    db.commit()
    return {"status": "ok", "message": "Node recertified"}


@app.get("/tasks")
def list_tasks(status: str = "IN_PROGRESS,PENDING", db: Session = Depends(get_db)):
    statuses = [s.strip() for s in status.split(",")]
    tasks = db.query(EscalationTask).filter(EscalationTask.status.in_(statuses)).all()
    return [{"id": str(t.id), "node_id": str(t.node_id), "status": t.status,
             "notes": t.notes, "deadline": t.deadline.isoformat() if t.deadline else None} for t in tasks]


@app.get("/audit")
def list_audit(limit: int = 30, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": str(l.id), "node_id": str(l.node_id), "event_type": l.event_type,
             "payload": l.event_payload, "created_at": l.created_at.isoformat()} for l in logs]


# ── Admin Reset (demo cleanup) ────────────────────────────
@app.post("/admin/reset")
def admin_reset(db: Session = Depends(get_db)):
    """Delete all demo‑environment nodes and dependent records."""
    demo_nodes = db.query(Node.node_id).filter(Node.environment == "demo").subquery()
    db.query(EscalationTask).filter(EscalationTask.node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(AuditLog).filter(AuditLog.node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(DependencyEdge).filter(DependencyEdge.parent_node_id.in_(demo_nodes)).delete(synchronize_session='fetch')
    db.query(Node).filter(Node.environment == "demo").delete()
    db.query(CostConfig).filter(CostConfig.environment == "demo").delete()
    db.commit()
    return {"status": "ok", "message": "All demo data cleared. Production data untouched."}


# ── Health / Metrics ──────────────────────────────────────
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health")
def health():
    return {"status": "ok"}
