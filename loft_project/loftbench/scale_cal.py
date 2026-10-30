"""Second follow-up to scale.py: flow-level calibration and client weighting at K = 6 / 9.

DualGuard demotes an entry whenever its score reaches tau at any poll under table pressure, so a
long-lived benign flow (IoT telemetry) gets many chances to cross tau. The row-level threshold
(1 % of sampled benign rows) ignores that. Flow-level calibration sets tau per controller so that
at most b % of the benign flows in its validation episodes ever reach it (b = 1 or 5), using
each flow's maximum score over all polls.

Training variants (MLP, 2 training seeds): local, pooled, FedAvg, FedProx (mu 0.01), and
FedProx with the client average weighted by benign row count (bw, favours the IoT clients)
or uniformly (uni). Calibrations: row (1 % of rows; FedAvg, FedProx, local and pooled rows
come from scale.py / scale_fed.py), flow1, flow5.

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.scale_cal [--workers 4]

Writes results/scale/{cal_offline.csv, cal_online.csv, cal_taus.json}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import scale, v21
from .config import VARIANTS
from .models import threshold_at_fpr, train_federated, train_local
from .sim import run_episode
from .scale import BUDGET, COLLECT_CFG, EXPOSURE, OUT, PROFILES, SPLITS, _ctrl
from .traffic import build_traffic

KS = (6, 9)
SEEDS = (0, 1)
ONLINE_SEEDS = (8000, 8001)
FLOW_BUDGETS = {"flow1": 0.01, "flow5": 0.05}
FED = {"fedavg": dict(mu=0.0), "prox": dict(mu=0.01),
       "prox_bw": dict(mu=0.01, weights="benign"), "prox_uni": dict(mu=0.01, weights="uniform")}
_M = scale._M


def _train_task(args):
    kind, k, c, s = args
    data = _M["data"]
    if kind == "local":
        tr = data[("train", c)]
        return args, train_local(tr.X, tr.y, epochs=30, seed=s)
    cs = _ctrl(k)
    Xs = [data[("train", o)].X for o in cs]
    ys = [data[("train", o)].y for o in cs]
    if kind == "pooled":
        return args, train_local(np.concatenate(Xs), np.concatenate(ys), epochs=30, seed=s)
    cfg = dict(FED[kind])
    w = cfg.pop("weights", None)
    if w == "benign":
        w = [float((y == 0).sum()) for y in ys]
    elif w == "uniform":
        w = [1.0] * len(ys)
    return args, train_federated(list(zip(Xs, ys)), rounds=30, seed=s, weights=w, **cfg)[0]


def _val_task(args):
    """Max score of every benign flow over all polls of one validation episode, per model."""
    c, v, seed = args
    prof, idx = PROFILES[c]
    tr = build_traffic(prof, idx, VARIANTS[v] if v else None, seed, COLLECT_CFG.duration,
                       COLLECT_CFG.attack_start)
    models = {key: m for key, m in _M["base"].items() if key[2] == c}
    mx = {key: np.full(tr.n_flows, -1.0) for key in models}

    def hook(t, fids, obs, lab):
        ben = lab == 0
        if not ben.any():
            return
        f, X = fids[ben], obs["X"][ben]
        for key, m in models.items():
            np.maximum.at(mx[key], f, m.predict_proba(X))

    run_episode(tr, COLLECT_CFG, collect=hook, record_ts=False)
    return {key: a[a >= 0] for key, a in mx.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t0 = time.time()
    data = scale.collect(a.workers)
    _M["data"] = data
    print(f"[collect] {time.time() - t0:.0f} s", flush=True)
    tasks = [("local", 0, c, s) for c in PROFILES for s in SEEDS]
    tasks += [(kind, k, "", s) for kind in ["pooled"] + list(FED) for k in KS for s in SEEDS]
    trained = {}
    with get_context("fork").Pool(a.workers) as p:
        for key, m in p.imap_unordered(_train_task, tasks):
            trained[key] = m
    base = {}                       # (kind, K, controller, seed) -> model
    for k in KS:
        for c in _ctrl(k):
            for s in SEEDS:
                base[("local", k, c, s)] = trained[("local", 0, c, s)]
                for kind in ["pooled"] + list(FED):
                    base[(kind, k, c, s)] = trained[(kind, k, "", s)]
    _M["base"] = base
    print(f"[train] {time.time() - t0:.0f} s", flush=True)

    vt = [(c, v, s) for c in PROFILES for s in SPLITS["val"] for v in list(EXPOSURE[c]) + [None]]
    with get_context("fork").Pool(a.workers) as p:
        parts = p.map(_val_task, vt)
    flowmax = {}
    for d in parts:
        for key, arr in d.items():
            flowmax.setdefault(key, []).append(arr)
    M, taus = {}, {}
    for key, m in base.items():
        kind, k, c, s = key
        v = data[("val", c)]
        row_tau = threshold_at_fpr(m.predict_proba(v.X[v.y == 0]), BUDGET)
        fm = np.concatenate(flowmax[key])
        cal = {"row": row_tau, **{n: threshold_at_fpr(fm, b) for n, b in FLOW_BUDGETS.items()}}
        for n, tau in cal.items():
            if n == "row" and kind not in ("prox_bw", "prox_uni"):
                continue                      # already run in scale.py / scale_fed.py
            M[(f"{kind}|{n}", k, c, s)] = (m, tau)
        taus["/".join(map(str, key))] = cal
        taus["/".join(map(str, key))]["benign_flows"] = int(len(fm))
    json.dump(taus, open(os.path.join(OUT, "cal_taus.json"), "w"), indent=1)
    print(f"[calibrate] {time.time() - t0:.0f} s", flush=True)

    pd.DataFrame(scale.offline(data, M)).to_csv(os.path.join(OUT, "cal_offline.csv"), index=False)
    print(f"[offline] {time.time() - t0:.0f} s", flush=True)
    del data, parts
    _M.pop("data", None)
    sel = json.load(open("results/v21/selected.json"))["selected"]
    _M.update(models=M, pol=v21._policy(sel))
    # Local models do not depend on K: run them once (K = 9 contains every controller).
    eps = [(kind, k, c, s, v, sd) for (kind, k, c, s) in M
           if not (kind.startswith("local") and k != 9) for v in VARIANTS for sd in ONLINE_SEEDS]
    print(f"[online] {len(eps)} episodes", flush=True)
    with get_context("fork").Pool(a.workers) as p:
        rows = p.map(scale._episode, eps, chunksize=4)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "cal_online.csv"), index=False)
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
