import time
import uuid
import numpy as np
from typing import Dict, Tuple

# --- Configuration & Constraints ---
ENDPOINTS = ["HDFC", "ICICI", "SBI"]

# Hard bounds to prevent complete starvation or overwhelming an endpoint
FLOORS = {"HDFC": 0.05, "ICICI": 0.05, "SBI": 0.05}
CEILINGS = {"HDFC": 0.80, "ICICI": 0.60, "SBI": 0.50}  # e.g., SBI has lower capacity

# Max delta prevents the model from shifting too much traffic in a single tick
MAX_DELTA = 0.20  

# Global state to track previous tick's weights
_previous_weights = {"HDFC": 0.33, "ICICI": 0.33, "SBI": 0.34}

def fetch_features(payment_id: str) -> Dict[str, float]:
    """Mock O(1) read from Redis (Feature Store)"""
    return {
        "HDFC_success_rate_10s": 0.99,
        "ICICI_success_rate_10s": 0.95,
        "SBI_success_rate_10s": 0.50, # Simulating an issue at SBI
        "HDFC_latency_ms": 150.0,
        "ICICI_latency_ms": 200.0,
        "SBI_latency_ms": 2500.0,
    }

def model_inference(features: Dict[str, float]) -> Dict[str, float]:
    """
    Mock ML inference (e.g., Logistic Regression or GBM).
    Returns raw unconstrained preference scores based on features.
    """
    # The model detects SBI is failing and outputs a hallucinated/extreme score
    return {
        "HDFC": 0.85, 
        "ICICI": 0.15,
        "SBI": 0.00   # Model wants to kill all traffic to SBI
    }

def deterministic_allocator(raw_scores: Dict[str, float], prev_weights: Dict[str, float]) -> Dict[str, float]:
    """
    The Gating Mechanism.
    Enforces boundaries: floors, ceilings, and max rate of change.
    """
    gated = {}
    
    for ep in ENDPOINTS:
        score = raw_scores.get(ep, 0.0)
        
        # 1. Apply Floor and Ceiling
        clamped = max(FLOORS[ep], min(score, CEILINGS[ep]))
        
        # 2. Apply Rate-of-Change Limiter (max_delta)
        prev = prev_weights.get(ep, 0.0)
        if clamped > prev + MAX_DELTA:
            clamped = prev + MAX_DELTA
        elif clamped < prev - MAX_DELTA:
            clamped = prev - MAX_DELTA
            
        gated[ep] = clamped

    # 3. Renormalize so weights sum to 1.0
    total = sum(gated.values())
    if total == 0:
        return {ep: 1.0 / len(ENDPOINTS) for ep in ENDPOINTS} # Fallback
        
    normalized = {ep: round(val / total, 4) for ep, val in gated.items()}
    return normalized

def route_payment(payment_id: str) -> Tuple[str, Dict]:
    """The hot path for payment routing."""
    start_time = time.perf_counter()
    
    # 1. Feature Fetch
    features = fetch_features(payment_id)
    
    # 2. Score
    raw_scores = model_inference(features)
    
    # 3. Apply Gates
    global _previous_weights
    gated_weights = deterministic_allocator(raw_scores, _previous_weights)
    _previous_weights = gated_weights.copy()
    
    # 4. Execute Probabilistic Selection
    endpoints = list(gated_weights.keys())
    probabilities = np.array(list(gated_weights.values()))
    probabilities /= probabilities.sum() # Ensure exact sum of 1.0
    selected = np.random.choice(endpoints, p=probabilities)
    
    latency_ms = (time.perf_counter() - start_time) * 1000

    # 5. Construct Audit Payload (to be pushed to Kafka async)
    audit_payload = {
        "timestamp": time.time(),
        "payment_id": payment_id,
        "decision_id": str(uuid.uuid4()),
        "latency_ms": round(latency_ms, 2),
        "raw_model_weights": raw_scores,
        "final_gated_weights": gated_weights,
        "selected_endpoint": selected,
    }
    
    return selected, audit_payload

if __name__ == "__main__":
    print("\n--- Simulating Real-Time Payment Routing ---")
    print(f"Initial State: {_previous_weights}\n")
    
    # Simulate a few sequential transactions to watch the allocator in action
    for i in range(1, 4):
        payment_id = f"pay_XYZ123_tick{i}"
        selected, audit = route_payment(payment_id)
        
        print(f"Transaction {i} | Selected: {selected}")
        print(f"Model Requested : {audit['raw_model_weights']}")
        print(f"Gated Enforced  : {audit['final_gated_weights']}")
        print(f"Latency         : {audit['latency_ms']} ms\n")
