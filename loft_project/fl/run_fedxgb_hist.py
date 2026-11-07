"""Lossless (histogram-based) federated XGBoost, FEVER's real-traffic controllers
(docs/realfl_plan.md, section added 8 November).

Three worker processes (C1, C2, C3), each loading only its own rows. XGBoost's collective
(RabitTracker on this machine) merges the workers' quantile sketches into shared feature bins and,
for every tree node, adds the workers' per-bin gradient and hessian sums (allreduce); every worker
then picks the same split. No rows or labels leave a worker. Same settings as pooled XGBoost.

    ~/.venvs/fl/bin/python fl/run_fedxgb_hist.py     # writes results/realfl/fedxgb_hist.json, fedxgb_hist_log.json
"""
import json
import multiprocessing as mp
import sys
import time

OUT = "results/realfl"
CLIENTS = ("C1", "C2", "C3")
TREES = 300
PARAMS = dict(objective="binary:logistic", eta=0.1, max_depth=6, tree_method="hist", max_bin=256,
              nthread=1, eval_metric="logloss", seed=0)


def lo_bytes():
    """Bytes sent on the loopback interface (all workers and the tracker run on this machine)."""
    for line in open("/proc/net/dev"):
        if line.strip().startswith("lo:"):
            return int(line.split(":")[1].split()[8])
    return 0


def worker(name, args, q):
    import numpy as np
    import xgboost as xgb
    z = np.load(f"{OUT}/fl_data/{name}.npz")
    with xgb.collective.CommunicatorContext(**args):
        rank = xgb.collective.get_rank()
        dtrain = xgb.DMatrix(z["X"], label=z["y"])
        t0 = time.time()
        bst = xgb.train(PARAMS, dtrain, num_boost_round=TREES)
        if rank == 0:
            bst.save_model(f"{OUT}/fedxgb_hist.json")
        q.put(dict(client=name, rank=rank, rows=int(dtrain.num_row()), seconds=round(time.time() - t0, 1),
                   trees=bst.num_boosted_rounds(), features=int(dtrain.num_col())))


if __name__ == "__main__":
    from xgboost.tracker import RabitTracker
    t0, b0 = time.time(), lo_bytes()
    tracker = RabitTracker(host_ip="127.0.0.1", n_workers=len(CLIENTS))
    tracker.start()
    args = tracker.worker_args()
    q = mp.get_context("spawn").Queue()
    ps = [mp.get_context("spawn").Process(target=worker, args=(c, args, q)) for c in CLIENTS]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    tracker.wait_for(timeout=60)
    sent = lo_bytes() - b0
    info = sorted((q.get() for _ in CLIENTS), key=lambda r: r["client"])
    d = info[0]["features"]
    log = dict(workers=info, seconds=round(time.time() - t0, 1), loopback_bytes=sent,
               loopback_bytes_per_tree=round(sent / TREES),
               histogram_bytes=d * PARAMS["max_bin"] * 2 * 8)   # one node's gradient/hessian sums (double)
    json.dump(log, open(f"{OUT}/fedxgb_hist_log.json", "w"), indent=1)
    print(json.dumps(log, indent=1))
    sys.exit(0 if all(p.exitcode == 0 for p in ps) else 1)
