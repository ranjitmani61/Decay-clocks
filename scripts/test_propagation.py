import sys, os
sys.path.insert(0, os.path.expanduser("~/decay-clocks"))
from src.core.models.node import Node, NodeClass, Criticality, DependencyEdge, AuditLog, EscalationTask
from src.core.scheduler.runner import run_scheduled_cycle
from src.core.api.database import SessionLocal
from src.core.api.catalogue import get_catalogue
from datetime import datetime, timezone

db = SessionLocal()

# Clear previous test data in dependency order
db.query(EscalationTask).delete()
db.query(AuditLog).delete()
db.query(DependencyEdge).delete()
db.query(Node).delete()
db.commit()

parent = Node(node_class=NodeClass.ETL_TRANSFORM, version_ref="etl-v1",
              owner_team="data", criticality=Criticality.HIGH, domain_tags=["EU"], decay_alpha=0.01)
child = Node(node_class=NodeClass.ML_MODEL, version_ref="ml-v1",
             owner_team="risk", criticality=Criticality.HIGH, domain_tags=["EU"], decay_alpha=0.01)
db.add_all([parent, child])
db.commit()

edge = DependencyEdge(parent_node_id=parent.node_id, child_node_id=child.node_id,
                      edge_type="SCHEMA_DEP", propagation_coeffs={"R_s": 0.9})
db.add(edge)
db.commit()

# Degrade parent structural axis
parent.r_s = 0.2
db.commit()

print(f"Before: parent R_s={parent.r_s}, child R_s={child.r_s}")

now = datetime.now(timezone.utc)
catalogue = get_catalogue()
run_scheduled_cycle(db=db, catalogue=catalogue, now=now)

db.refresh(child)
print(f"After : child R_s={child.r_s} (should be {parent.r_s})")
print(f"Child status: {child.status.value}")

db.close()
