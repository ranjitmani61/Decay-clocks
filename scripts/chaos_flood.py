#!/usr/bin/env python3
"""Chaos test: flood the API with regulatory signals and observe surge‑calm."""
import time, random, uuid, requests
from datetime import datetime, timezone

API = "http://localhost:8000"
NUM_NODES = 50          # create 50 nodes
SIGNALS_PER_SECOND = 10 # send 10 signals/second
DURATION_SECONDS = 30   # run for 30 seconds

# 1. Create nodes
node_ids = []
for i in range(NUM_NODES):
    resp = requests.post(f"{API}/nodes", json={
        "node_class": "ML_MODEL",
        "version_ref": f"v{i}",
        "owner_team": random.choice(["risk","compliance","fraud"]),
        "criticality": "HIGH",
        "domain_tags": ["EU"],
        "decay_alpha": 0.01,
    })
    if resp.status_code == 201:
        node_ids.append(resp.json()["node_id"])
print(f"Created {len(node_ids)} nodes")

# 2. Flood signals
print(f"Flooding {SIGNALS_PER_SECOND} signals/sec for {DURATION_SECONDS}s...")
start = time.time()
sent = 0
while time.time() - start < DURATION_SECONDS:
    for _ in range(SIGNALS_PER_SECOND):
        ev = {
            "type": "regulatory",
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": 0.9,
            "domain_tags": ["EU"],
        }
        requests.post(f"{API}/signals/ingest", json={"raw_events":[ev]})
        sent += 1
    time.sleep(1)

# 3. Check metrics
resp = requests.get(f"{API}/metrics")
print(f"\nSent {sent} signals")
print("Metrics snapshot (first 500 chars):")
print(resp.text[:500])
