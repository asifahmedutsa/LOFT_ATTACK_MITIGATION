"""Federated XGBoost with Flower (bagging), FEVER's real-traffic controllers (docs/realfl_plan.md).

One Flower server and three client processes (C1, C2, C3) on this machine, talking over gRPC.
Each client reads only its own rows (results/realfl/fl_data/<C>.npz). Every round the server sends
the global model; each client adds LOCAL_ROUNDS trees trained on its own rows and returns only
those trees; the server appends all clients' new trees to the global model (FedXgbBagging).

    ~/.venvs/fl/bin/python fl/run_fedxgb.py            # writes results/realfl/fedxgb.json, fedxgb_log.json

Runs in its own environment (~/.venvs/fl: flwr 1.20.0, xgboost 3.4.1).
"""
import json
import os
import subprocess
import sys
import time

OUT = "results/realfl"
ADDR = "127.0.0.1:8099"
ROUNDS, LOCAL_ROUNDS = 100, 1        # FedXgbBagging keeps one new tree per client per round
# --cyclic (exploratory, not in docs/realfl_plan.md's choice rule): FedXgbCyclic passes one model
# from client to client; each round one client adds CYC_LOCAL trees on its own rows and returns the
# whole model. 100 rounds x 3 trees = 300 trees, as the bagging model.
CYCLIC = "--cyclic" in sys.argv
CYC_LOCAL = 3
NAME = "fedxgb_cyclic" if CYCLIC else "fedxgb"
PARAMS = dict(objective="binary:logistic", eta=0.1, max_depth=6, tree_method="hist", nthread=2,
              eval_metric="logloss", seed=0)


def server():
    import flwr as fl
    from flwr.common import parameters_to_ndarrays  # noqa: F401
    from flwr.server.strategy import FedXgbBagging, FedXgbCyclic

    log = []

    class Saving(FedXgbCyclic if CYCLIC else FedXgbBagging):
        def aggregate_fit(self, rnd, results, failures):
            params, metrics = super().aggregate_fit(rnd, results, failures)
            if params is not None:
                raw = bytes(params.tensors[0])
                with open(f"{OUT}/{NAME}.json", "wb") as f:
                    f.write(raw)
                log.append(dict(round=rnd, clients=len(results), failures=len(failures), model_bytes=len(raw),
                                sent_bytes=sum(len(r.parameters.tensors[0]) for _, r in results),
                                time=round(time.time() - t0, 2)))
                json.dump(log, open(f"{OUT}/{NAME}_log.json", "w"), indent=1)
            return params, metrics

    t0 = time.time()
    if CYCLIC:
        strategy = Saving(fraction_fit=1.0, min_available_clients=3, fraction_evaluate=0.0, min_evaluate_clients=0)
    else:
        strategy = Saving(fraction_fit=1.0, min_fit_clients=3, min_available_clients=3, fraction_evaluate=0.0,
                          min_evaluate_clients=0)
    fl.server.start_server(server_address=ADDR, config=fl.server.ServerConfig(num_rounds=ROUNDS), strategy=strategy)


def client(name):
    import flwr as fl
    import numpy as np
    import xgboost as xgb
    from flwr.common import Code, FitIns, FitRes, Parameters, Status

    z = np.load(f"{OUT}/fl_data/{name}.npz")
    dtrain = xgb.DMatrix(z["X"], label=z["y"])

    class C(fl.client.Client):
        def fit(self, ins: FitIns) -> FitRes:
            glob = ins.parameters.tensors
            if not glob or len(glob[0]) == 0:
                bst = xgb.train(PARAMS, dtrain, num_boost_round=CYC_LOCAL if CYCLIC else LOCAL_ROUNDS)
                new = bst
            else:
                bst = xgb.Booster(params=PARAMS)
                bst.load_model(bytearray(glob[0]))
                n0 = bst.num_boosted_rounds()
                for i in range(CYC_LOCAL if CYCLIC else LOCAL_ROUNDS):
                    bst.update(dtrain, n0 + i)
                # bagging: only this client's new trees; cyclic: the whole model goes on
                new = bst if CYCLIC else bst[n0:bst.num_boosted_rounds()]
            raw = new.save_raw("json")
            return FitRes(status=Status(code=Code.OK, message="OK"),
                          parameters=Parameters(tensor_type="", tensors=[bytes(raw)]),
                          num_examples=int(dtrain.num_row()), metrics={})

    for _ in range(60):
        try:
            fl.client.start_client(server_address=ADDR, client=C())
            return
        except Exception:
            time.sleep(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--cyclic"]
    if args:
        server() if args[0] == "server" else client(args[0])
        sys.exit(0)
    t0 = time.time()
    me = os.path.abspath(__file__)
    flag = ["--cyclic"] if CYCLIC else []
    srv = subprocess.Popen([sys.executable, me, "server"] + flag)
    time.sleep(3)
    cls = [subprocess.Popen([sys.executable, me, c] + flag) for c in ("C1", "C2", "C3")]
    for p in cls:
        p.wait()
    srv.wait(timeout=120)
    print(f"federated XGBoost ({NAME}): {ROUNDS} rounds, {time.time() - t0:.0f} s")
