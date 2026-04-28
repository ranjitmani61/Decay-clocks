"""Locust load test for Decay Clocks API."""
import random
import uuid
from datetime import datetime, timezone
from locust import HttpUser, task, between

class DecayClocksUser(HttpUser):
    wait_time = between(1, 3)
    def on_start(self):
        self.node_ids = []

    @task(3)
    def create_node(self):
        payload = {
            "node_class": random.choice(["ML_MODEL", "BUSINESS_RULE_SET", "API_CONTRACT"]),
            "version_ref": f"v{random.randint(1,100)}",
            "owner_team": random.choice(["risk", "compliance", "fraud"]),
            "criticality": random.choice(["HIGH", "STANDARD"]),
            "domain_tags": random.sample(["EU", "US", "credit", "GDPR"], k=random.randint(1,2)),
            "decay_alpha": round(random.uniform(0.005, 0.02), 4),
        }
        with self.client.post("/nodes", json=payload, catch_response=True) as resp:
            if resp.status_code == 201:
                data = resp.json()
                self.node_ids.append(data["node_id"])
            else:
                resp.failure(f"Create node failed: {resp.status_code}")

    @task(5)
    def get_node(self):
        if not self.node_ids:
            return
        node_id = random.choice(self.node_ids)
        self.client.get(f"/nodes/{node_id}", name="/nodes/{id}")

    @task(2)
    def ingest_signals(self):
        if not self.node_ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "raw_events": [{
                "type": "regulatory",
                "event_id": str(uuid.uuid4()),
                "timestamp": now,
                "severity": round(random.uniform(0.1, 0.9), 2),
                "domain_tags": random.sample(["EU", "US", "GDPR"], k=1),
            }]
        }
        self.client.post("/signals/ingest", json=payload)

    @task(1)
    def health(self):
        self.client.get("/health")
