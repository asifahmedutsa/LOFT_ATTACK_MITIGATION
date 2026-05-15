import flwr as fl
import numpy as np
import json
import os
from typing import List, Tuple, Dict, Optional
from flwr.common import Metrics

def weighted_average(metrics: List[Tuple[int, Metrics]]) -> Metrics:
    """Aggregate metrics from all clients using weighted average"""
    accuracies  = [num * m["accuracy"]  for num, m in metrics]
    precisions  = [num * m["precision"] for num, m in metrics]
    recalls     = [num * m["recall"]    for num, m in metrics]
    f1_scores   = [num * m["f1_score"]  for num, m in metrics]
    examples    = [num for num, _ in metrics]

    return {
        "accuracy" : sum(accuracies)  / sum(examples),
        "precision": sum(precisions)  / sum(examples),
        "recall"   : sum(recalls)     / sum(examples),
        "f1_score" : sum(f1_scores)   / sum(examples),
    }

def get_strategy():
    return fl.server.strategy.FedAvg(
        fraction_fit=1.0,           # Use all clients every round
        fraction_evaluate=1.0,
        min_fit_clients=3,          # Wait for all 3 controllers
        min_evaluate_clients=3,
        min_available_clients=3,
        evaluate_metrics_aggregation_fn=weighted_average,
        fit_metrics_aggregation_fn=weighted_average,
    )

if __name__ == "__main__":
    print("="*50)
    print("  Federated Learning Server Starting...")
    print("  Waiting for 3 controllers to connect...")
    print("="*50)

    home = os.path.expanduser("~")
    strategy = get_strategy()

    history = fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=3),
        strategy=strategy,
    )

    print("\n" + "="*50)
    print("  Federated Learning Complete!")
    print("="*50)

    # Save global results
    results = {
        "rounds": len(history.metrics_distributed),
        "final_metrics": {
            k: float(v[-1][1]) if history.metrics_distributed.get(k) else 0
            for k, v in history.metrics_distributed.items()
        }
    }

    out = f"{home}/loft_project/federated/global_results.json"
    os.makedirs(f"{home}/loft_project/federated", exist_ok=True)
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"[+] Global results saved to {out}")