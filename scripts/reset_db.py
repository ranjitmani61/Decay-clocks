"""Clear all nodes and dependent rows for a clean demo."""
import sys, os
sys.path.insert(0, os.path.expanduser("~/decay-clocks"))

from src.core.api.database import SessionLocal
from src.core.models.node import EscalationTask, AuditLog, DependencyEdge, Node

db = SessionLocal()
db.query(EscalationTask).delete()
db.query(AuditLog).delete()
db.query(DependencyEdge).delete()
db.query(Node).delete()
db.commit()
db.close()
print("All nodes cleared.")
