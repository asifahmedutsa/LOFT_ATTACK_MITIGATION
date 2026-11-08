"""Lossless (histogram-based) federated XGBoost, FEVER's real-traffic controllers
(docs/realfl_plan.md, sections added 8 November).

Three worker processes (C1, C2, C3), each loading only its own rows. XGBoost's collective
(RabitTracker on this machine) merges the workers' quantile sketches into shared feature bins and,
for every tree node, adds the workers' per-bin gradient and hessian sums (allreduce); every worker
then picks the same split. No rows or labels leave a worker. Same settings as pooled XGBoost.

    ~/.venvs/fl/bin/python fl/run_fedxgb_hist.py          # writes <FL_OUT>/fedxgb_hist.json, fedxgb_hist_log.json
    ~/.venvs/fl/bin/python fl/run_fedxgb_hist.py --drop   # dropped-controller test (drop_test.json; the T1B check
                                                          # is in loftbench.realfl_confirm)

FL_DATA, FL_OUT and FL_SEED choose the controllers' data, the output folder and the model seed; FL_TREES,
FL_PARAMS (JSON, merged into PARAMS) and FL_NAME train another detector's model the same way.
"""
import json
import multiprocessing as mp
import os
import sys
import time

OUT = os.environ.get("FL_OUT", "results/realfl")
DATA = os.environ.get("FL_DATA", f"{OUT}/fl_data")
SEED = int(os.environ.get("FL_SEED", "0"))
CLIENTS = ("C1", "C2", "C3")
TREES = int(os.environ.get("FL_TREES", "300"))
NAME = os.environ.get("FL_NAME", "fedxgb_hist")     # output files <NAME>.json, <NAME>_log.json
CKPT, KILL, KILL_AT = 50, "C2", 150            # dropped-controller test
PARAMS = dict(objective="binary:logistic", eta=0.1, max_depth=6, tree_method="hist", max_bin=256,
              nthread=1, eval_metric="logloss", seed=SEED)
PARAMS.update(json.loads(os.environ.get("FL_PARAMS", "{}")))   # another detector's settings (exploratory runs)


def lo_bytes():
    """Bytes sent on the loopback interface (all workers and the tracker run on this machine)."""
    for line in open("/proc/net/dev"):
        if line.strip().startswith("lo:"):
            return int(line.split(":")[1].split()[8])
    return 0


def worker(name, args, q, out, rounds, start=None, kill=False):
    import numpy as np
    import xgboost as xgb

    class Checkpoint(xgb.callback.TrainingCallback):
        def after_iteration(self, model, epoch, evals_log):
            n = model.num_boosted_rounds()
            if kill and n % CKPT == 0:
                model.save_model(f"{OUT}/drop_ckpt_{name}_{n}.json")
            if kill and name == KILL and n == KILL_AT:
                os._exit(1)                     # this controller drops out
            return False

    z = np.load(f"{DATA}/{name}.npz")
    with xgb.collective.CommunicatorContext(**args):
        rank = xgb.collective.get_rank()
        dtrain = xgb.DMatrix(z["X"], label=z["y"])
        t0 = time.time()
        bst = xgb.train(PARAMS, dtrain, num_boost_round=rounds, xgb_model=start, callbacks=[Checkpoint()])
        if rank == 0:
            bst.save_model(out)
        q.put(dict(client=name, rank=rank, rows=int(dtrain.num_row()), seconds=round(time.time() - t0, 1),
                   trees=bst.num_boosted_rounds(), features=int(dtrain.num_col())))


def session(out, rounds, start=None, kill=False, timeout=None):
    """One training session: a tracker and three worker processes. Returns the workers' exit codes."""
    from xgboost.tracker import RabitTracker
    tracker = RabitTracker(host_ip="127.0.0.1", n_workers=len(CLIENTS), sortby="task")   # ranks C1, C2, C3 every session
    tracker.start()
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=worker, args=(c, dict(tracker.worker_args(), dmlc_task_id=c), q, out, rounds, start, kill))
          for c in CLIENTS]
    for p in ps:
        p.start()
    for p in ps:
        p.join(timeout)
    for p in ps:
        if p.is_alive():
            p.terminate()
            p.join()
    info = []
    while not q.empty():
        info.append(q.get())
    return [p.exitcode for p in ps], sorted(info, key=lambda r: r["client"])


def train():
    time.sleep(1)
    i0, t_idle = lo_bytes(), time.time()
    time.sleep(30)
    idle_rate = (lo_bytes() - i0) / (time.time() - t_idle)
    t0, b0 = time.time(), lo_bytes()
    codes, info = session(f"{OUT}/{NAME}.json", TREES)
    secs = time.time() - t0
    sent = lo_bytes() - b0 - idle_rate * secs
    d = info[0]["features"]
    log = dict(workers=info, seconds=round(secs, 1), loopback_bytes=round(sent), idle_bytes_per_s=round(idle_rate),
               loopback_bytes_per_tree=round(sent / TREES),
               histogram_bytes=d * PARAMS["max_bin"] * 2 * 8)   # one node's gradient/hessian sums (double)
    json.dump(log, open(f"{OUT}/{NAME}_log.json", "w"), indent=1)
    print(json.dumps(log, indent=1))
    return all(c == 0 for c in codes)


def drop_test():
    """Train with checkpoints; C2 drops after tree 150; everyone restarts from the last checkpoint."""
    import numpy as np
    import xgboost as xgb
    full = f"{OUT}/drop_full.json"
    codes0, _ = session(full, TREES)
    codes1, _ = session(f"{OUT}/drop_partial.json", TREES, kill=True, timeout=120)
    ck = f"{OUT}/drop_ckpt_C1_{KILL_AT}.json"
    have = xgb.Booster(model_file=ck).num_boosted_rounds()
    codes2, _ = session(f"{OUT}/drop_resumed.json", TREES - have, start=ck)
    X = np.concatenate([np.load(f"{DATA}/{c}.npz")["X"] for c in CLIENTS])
    a = xgb.Booster(model_file=full).predict(xgb.DMatrix(X))
    b = xgb.Booster(model_file=f"{OUT}/drop_resumed.json")
    diff = float(np.abs(a - b.predict(xgb.DMatrix(X))).max())
    r = dict(uninterrupted_exit=codes0, interrupted_exit=codes1, checkpoint_trees=have, resumed_exit=codes2,
             resumed_trees=b.num_boosted_rounds(), max_abs_diff_training_rows=diff)
    json.dump(r, open(f"{OUT}/drop_test.json", "w"), indent=1)
    print(json.dumps(r, indent=1))
    for f in os.listdir(OUT):
        if f.startswith(("drop_ckpt_", "drop_partial")):     # the full and resumed models are kept
            os.remove(f"{OUT}/{f}")
    return diff <= 1e-6


if __name__ == "__main__":
    sys.exit(0 if (drop_test() if "--drop" in sys.argv else train()) else 1)
