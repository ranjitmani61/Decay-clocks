"""Shared helper to load the active cost configuration."""
from sqlalchemy.orm import Session
from src.core.models.node import CostConfig


def get_active_cost_config(db: Session) -> dict:
    """Return the currently active cost configuration from the database."""
    row = db.query(CostConfig).filter(CostConfig.active == True).first()
    if not row:
        # Fallback to production defaults
        return {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": 500.0,
            "C_int": 1000.0,
            "provisional_hazard": 0.2,
            "floor_axes": {"r": 0.2, "s": 0.3},
            "hazard_mode": "linear",
            "dominant_axes": [],
        }
    return {
        "weights": row.weights,
        "C_err": row.C_err,
        "C_int": row.C_int,
        "provisional_hazard": row.provisional_hazard,
        "floor_axes": row.floor_axes,
        "hazard_mode": getattr(row, "hazard_mode", "linear") or "linear",
        "dominant_axes": getattr(row, "dominant_axes", []) or [],
    }
