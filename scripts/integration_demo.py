#!/usr/bin/env python3
"""Full governance demo – clean state via API, fully explainable."""
import requests

API = "http://localhost:8000"

# ---------- Step 0: Reset state via API ----------
print("🔄 Resetting database for a clean demo...")
requests.post(f"{API}/admin/reset")

# ---------- Step 1: Set demo cost config ----------
print("0️⃣  Setting demo cost config (provisional_hazard=0.10)...")
requests.post(f"{API}/config/cost", json={
    "weights": {"s":0.2, "p":0.2, "c":0.2, "r":0.2, "t":0.2},
    "C_err": 500.0,
    "C_int": 1000.0,
    "provisional_hazard": 0.10,
    "floor_axes": {"r":0.2, "s":0.3},
    "hazard_mode": "hard_gate",
    "dominant_axes": [{"axis": "r", "gate_threshold": 0.5}],
    "environment": "demo",
})

# ---------- Step 2: Register node ----------
print("1️⃣  Registering loan model node...")
resp = requests.post(f"{API}/nodes", json={
    "node_class": "ML_MODEL", "version_ref": "loan-model-v1",
    "owner_team": "credit-risk", "criticality": "HIGH",
    "domain_tags": ["EU"], "decay_alpha": 0.01, "environment": "demo",
})
node = resp.json()
nid = node["node_id"]
print(f"   Node ID: {nid}  Status: {node['status']}")

# ---------- Step 3: First loan decision ----------
print("\n2️⃣  Making loan decision (score 720, approved)...")
decision = {"score": 720, "approved": True}
resp = requests.post(f"{API}/decisions/wrap", json={"node_id": nid, "original_output": decision})
w = resp.json()["__provenance__"]
print(f"   Provisional: {w['provisional']}")
print(f"   Hazard     : {w.get('hazard', 'N/A')}")
print(f"   Threshold  : {w.get('threshold', 'N/A')}")
print(f"   Decision   : {w.get('decision', 'N/A')}")

# ---------- Step 4: Inject regulatory shock ----------
print("\n3️⃣  Injecting ECB regulatory signal...")
requests.post(f"{API}/signals/ingest", json={
    "raw_events": [{
        "type": "regulatory",
        "event_id": "demo-ecb",
        "timestamp": "2026-04-30T12:00:00Z",
        "severity": 0.9,
        "domain_tags": ["EU"],
    }]
})

# ---------- Step 5: Check node state ----------
print("\n4️⃣  Checking node state after signal...")
resp = requests.get(f"{API}/nodes/{nid}")
node = resp.json()
print(f"   Status      : {node['status']}")
print(f"   Reliability : {node['reliability']}")

# ---------- Step 6: Second loan decision ----------
print("\n5️⃣  Making another loan decision (score 680, approved)...")
decision2 = {"score": 680, "approved": True}
resp = requests.post(f"{API}/decisions/wrap", json={"node_id": nid, "original_output": decision2})
w2 = resp.json()["__provenance__"]
print(f"   Provisional: {w2['provisional']}")
print(f"   Status     : {w2['status']}")
print(f"   Hazard     : {w2.get('hazard', 'N/A')}")
print(f"   Threshold  : {w2.get('threshold', 'N/A')}")
print(f"   Decision   : {w2.get('decision', 'N/A')}")

# ---------- Step 7: State transition metrics ----------
print("\n6️⃣  State transition metrics:")
resp = requests.get(f"{API}/metrics")
for line in resp.text.split("\n"):
    if "state_transitions" in line and not line.startswith("# HELP") and not line.startswith("# TYPE"):
        print(f"   {line}")
