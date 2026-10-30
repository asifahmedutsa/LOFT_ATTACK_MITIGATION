"""Follow-up to scale.py: why does FedAvg harm more benign flows online at K = 6 and 9?

The K = 6 / 9 FedAvg models (30 rounds, 1 local epoch) keep the 1 % offline benign budget but
demote ~10x more benign entries online than the pooled model, mostly on the IoT controllers.
This compares federated training variants on the same data, controllers and thresholds rule:

  r100e1  100 rounds, 1 local epoch        (under-convergence?)
  r30e3   30 rounds, 3 local epochs
  prox    FedProx mu = 0.01, 30 rounds     (client drift on non-IID data?)
  ft      FedAvg r30e1, then 2 epochs of local fine-tuning per controller (personalisation)

The baseline (FedAvg r30e1) and pooled rows come from results/scale/online.csv, restricted to
the same episode seeds.

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.scale_fed [--workers 4]

Writes results/scale/{fed_offline.csv, fed_online.csv}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import copy
import json
import time
from multiprocessing import get_context

import pandas as pd

from . import scale, v21
from .config import VARIANTS
from .models import threshold_at_fpr, train_federated
from .scale import BUDGET, OUT, TRAIN_SEEDS, _ctrl

KS = (6, 9)
ONLINE_SEEDS = (8000, 8001)
CONFIGS = {"r100e1": dict(rounds=100, local_epochs=1, mu=0.0),
           "r30e3": dict(rounds=30, local_epochs=3, mu=0.0),
           "prox": dict(rounds=30, local_epochs=1, mu=0.01),
           "ft": dict(rounds=30, local_epochs=1, mu=0.0)}
_M = scale._M


def _train_task(args):
    cfg, k, s = args
    data = _M["data"]
    cs = _ctrl(k)
    m, comm, _ = train_federated([(data[("train", c)].X, data[("train", c)].y) for c in cs],
                                 seed=s, **CONFIGS[cfg])
    out = {}
    for c in cs:
        mc = m
        if cfg == "ft":
            mc = copy.deepcopy(m)
            tr = data[("train", c)]
            mc.fit(tr.X, tr.y, epochs=2, lr=1e-3, seed=s)
        v = data[("val", c)]
        out[(cfg, k, c, s)] = (mc, threshold_at_fpr(mc.predict_proba(v.X[v.y == 0]), BUDGET))
    return out, comm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    t0 = time.time()
    data = scale.collect(a.workers)
    _M["data"] = data
    print(f"[collect] {time.time() - t0:.0f} s", flush=True)
    M, comm = {}, {}
    tasks = [(cfg, k, s) for cfg in CONFIGS for k in KS for s in TRAIN_SEEDS]
    with get_context("fork").Pool(a.workers) as p:
        for (out, cm), t in zip(p.imap(_train_task, tasks), tasks):
            M.update(out)
            comm["/".join(map(str, t))] = cm
    print(f"[train] {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(scale.offline(data, M)).to_csv(os.path.join(OUT, "fed_offline.csv"), index=False)
    print(f"[offline] {time.time() - t0:.0f} s", flush=True)
    del data
    _M.pop("data", None)
    sel = json.load(open("results/v21/selected.json"))["selected"]
    _M.update(models=M, pol=v21._policy(sel))
    eps = [(cfg, k, c, s, v, sd) for (cfg, k, c, s) in M for v in VARIANTS for sd in ONLINE_SEEDS]
    print(f"[online] {len(eps)} episodes", flush=True)
    with get_context("fork").Pool(a.workers) as p:
        rows = p.map(scale._episode, eps, chunksize=4)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "fed_online.csv"), index=False)
    json.dump(comm, open(os.path.join(OUT, "fed_comm.json"), "w"), indent=1, default=str)
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
