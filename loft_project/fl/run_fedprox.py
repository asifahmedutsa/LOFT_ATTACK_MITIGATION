"""FedProx with Flower: FL-DualGuard's neural network (loftbench.models.MLP) on FEVER's real-traffic
controllers (docs/realfl_plan.md).

One Flower server and three client processes (C1, C2, C3) over gRPC; 30 rounds, one local epoch per
round, proximal term mu = 0.01 (as in FL-DualGuard). Feature scaling uses federated normalization:
each client contributes only its row count, feature sums and sums of squares.

    PYTHONPATH=. ~/.venvs/fl/bin/python fl/run_fedprox.py      # writes results/realfl/fedprox.npz, fedprox_log.json
    FL_MU=0 PYTHONPATH=. ~/.venvs/fl/bin/python fl/run_fedprox.py   # FedAvg: fedavg.npz, fedavg_log.json
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

OUT = os.environ.get("FL_OUT", "results/realfl")
DATA = os.environ.get("FL_DATA", f"{OUT}/fl_data")
SEED = int(os.environ.get("FL_SEED", "0"))
ADDR = "127.0.0.1:8098"
ROUNDS, HIDDEN = 30, 32
MU = float(os.environ.get("FL_MU", "0.01"))
NAME = "fedavg" if MU == 0 else "fedprox"     # FedProx with mu = 0 is FedAvg
CLIENTS = ("C1", "C2", "C3")


def scaler():
    """Federated normalization from the clients' sufficient statistics."""
    from loftbench.models import Standardizer
    st = []
    for c in CLIENTS:
        X = np.load(f"{DATA}/{c}.npz")["X"]
        st.append(Standardizer.stats(X))            # (n, sum, sum of squares) only
    return Standardizer.from_stats(st)


def server():
    import flwr as fl
    from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
    from flwr.server.strategy import FedProx

    from loftbench.models import MLP
    d = int(np.load(f"{DATA}/C1.npz")["X"].shape[1])
    init = MLP(d, HIDDEN, seed=SEED).get_weights()
    sc = scaler()
    log, t0 = [], time.time()

    class Saving(FedProx):
        def aggregate_fit(self, rnd, results, failures):
            params, metrics = super().aggregate_fit(rnd, results, failures)
            if params is not None:
                w = parameters_to_ndarrays(params)
                np.savez(f"{OUT}/{NAME}.npz", *w, mean=sc.mean, std=sc.std)
                log.append(dict(round=rnd, clients=len(results), failures=len(failures),
                                model_bytes=int(sum(a.nbytes for a in w)), time=round(time.time() - t0, 2)))
                json.dump(log, open(f"{OUT}/{NAME}_log.json", "w"), indent=1)
            return params, metrics

    strategy = Saving(proximal_mu=MU, fraction_fit=1.0, min_fit_clients=3, min_available_clients=3,
                      fraction_evaluate=0.0, min_evaluate_clients=0, initial_parameters=ndarrays_to_parameters(init))
    fl.server.start_server(server_address=ADDR, config=fl.server.ServerConfig(num_rounds=ROUNDS), strategy=strategy)


def client(name):
    import flwr as fl

    from loftbench.models import MLP
    z = np.load(f"{DATA}/{name}.npz")
    X, y = z["X"], z["y"]
    sc = scaler()
    k = CLIENTS.index(name)

    class C(fl.client.NumPyClient):
        def get_parameters(self, config):
            return MLP(X.shape[1], HIDDEN).get_weights()

        def fit(self, parameters, config):
            m = MLP(X.shape[1], HIDDEN)
            m.scaler = sc
            m.set_weights(parameters)
            rnd = int(config.get("server_round", 0))
            m.fit(X, y, epochs=1, seed=SEED * 1000 + rnd * 10 + k, prox_ref=[p.copy() for p in parameters],
                  mu=float(config.get("proximal_mu", MU)))
            return m.get_weights(), len(y), {}

    for _ in range(60):
        try:
            fl.client.start_client(server_address=ADDR, client=C().to_client())
            return
        except Exception:
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        server() if sys.argv[1] == "server" else client(sys.argv[1])
        sys.exit(0)
    t0 = time.time()
    me = os.path.abspath(__file__)
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    srv = subprocess.Popen([sys.executable, me, "server"], env=env)
    time.sleep(3)
    cls = [subprocess.Popen([sys.executable, me, c], env=env) for c in CLIENTS]
    for p in cls:
        p.wait()
    srv.wait(timeout=120)
    print(f"{NAME}: {ROUNDS} rounds, mu {MU}, {time.time() - t0:.0f} s")
