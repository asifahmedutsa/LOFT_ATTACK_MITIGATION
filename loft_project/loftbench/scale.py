"""Controller scaling: does federated learning keep helping as more controllers join?

Nine controller domains C1-C9 (three variants each of the enterprise, IoT and cloud profiles),
nested so that K = 3 uses C1-C3, K = 6 uses C1-C6 and K = 9 uses all. Each controller has
seen ONE attack variant in training (cycling A1, A2, A3, A4, A5, A7, A1, A2, A3); A6 is unseen by
all. For each K and each of 3 training seeds we train per controller a local MLP, the FedAvg
MLP over the K controllers and the pooled MLP (all raw data, upper bound), calibrate each
controller's threshold at the 1 % benign budget on its own validation runs, and measure

  offline: per controller and attack variant, precision / recall / F1 / AUC on held-out runs;
  online:  DualGuard (v2.1 policy) on every controller x attack variant, benign flows harmed.

Each attack is labelled per controller as seen-local, seen-remote (seen by another controller
of this federation) or unseen (by every controller of this federation), so the headline is how
the K controllers' protection against attacks they never saw themselves changes with K.

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.scale [--workers 4]

Writes results/scale/{dataset_summary.json, offline.csv, online.csv, train_info.json}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import time
from dataclasses import replace
from multiprocessing import get_context

import numpy as np

from . import v21
from .config import DOMAINS, VARIANTS, SimConfig
from .data import EXTRA_DOMAINS, Dataset, collect_run
from .defenses import DualGuard
from .models import threshold_at_fpr, train_federated, train_local
from .ports import assign_ports
from .sim import Defense, run_episode
from .traffic import build_traffic

OUT = "results/scale"
KS = (3, 6, 9)
TRAIN_SEEDS = (0, 1, 2)          # model initialisation / shuffling seeds
SPLITS = {"train": range(1000, 1005), "val": range(2000, 2003), "test_off": range(3000, 3004)}
ONLINE_SEEDS = range(8000, 8004)
COLLECT_CFG = SimConfig(duration=240.0)
ONLINE_CFG = SimConfig(duration=300.0)
BUDGET = 0.01
FED_ROUNDS = 30
EPOCHS = 30

E, I, C = DOMAINS["D1"], DOMAINS["D2"], DOMAINS["D3"]
# Domain indices 6-14 keep every controller's benign, host and pool address ranges disjoint
# from D1-D3 (0-2) and the trace domains (3-5).
PROFILES = {
    "C1": (replace(E, name="C1-enterprise"), 6),
    "C2": (replace(I, name="C2-iot"), 7),
    "C3": (replace(C, name="C3-cloud"), 8),
    "C4": (replace(E, name="C4-campus", new_flow_rate=110.0, n_clients=700,
                   mix={"dns": .30, "mice": .40, "elephant": .04, "periodic": .06,
                        "interactive": .20}), 9),
    "C5": (replace(I, name="C5-iot-dense", new_flow_rate=45.0, n_clients=2000,
                   mix={"dns": .20, "mice": .25, "elephant": .01, "periodic": .45,
                        "interactive": .09}, periodic_period=(3.0, 9.8)), 10),
    "C6": (replace(C, name="C6-cloud-heavy", new_flow_rate=80.0,
                   mix={"dns": .20, "mice": .45, "elephant": .10, "periodic": .08,
                        "interactive": .17}, flash_events=3, flash_rate=150.0), 11),
    "C7": (replace(E, name="C7-branch", new_flow_rate=70.0, n_clients=250,
                   mix={"dns": .45, "mice": .38, "elephant": .02, "periodic": .05,
                        "interactive": .10}), 12),
    "C8": (replace(I, name="C8-iot-fast", new_flow_rate=75.0, n_clients=900,
                   periodic_period=(1.5, 6.0)), 13),
    "C9": (replace(C, name="C9-cloud-light", new_flow_rate=55.0,
                   mix={"dns": .25, "mice": .50, "elephant": .06, "periodic": .07,
                        "interactive": .12}, flash_events=1), 14),
}
EXPOSURE = {c: (v,) for c, v in zip(PROFILES, ("A1", "A2", "A3", "A4", "A5", "A7", "A1", "A2", "A3"))}
EXTRA_DOMAINS.update(PROFILES)
_M = {}


def _ctrl(k):
    return list(PROFILES)[:k]


def exposure(c, v, k):
    if v in EXPOSURE[c]:
        return "seen-local"
    return "seen-remote" if any(v in EXPOSURE[o] for o in _ctrl(k)) else "unseen"


# ----------------------------------------------------------------------------
def _collect_task(args):
    split, c, v, s = args
    return split, c, collect_run(c, v, s, COLLECT_CFG)


def collect(workers):
    tasks = [(split, c, v, s) for split, seeds in SPLITS.items() for c in PROFILES for s in seeds
             for v in (list(VARIANTS) if split == "test_off" else list(EXPOSURE[c])) + [None]]
    parts = {}
    with get_context("fork").Pool(workers) as p:
        for split, c, ds in p.imap_unordered(_collect_task, tasks, chunksize=2):
            parts.setdefault((split, c), []).append(ds)
    data = {k: Dataset.concat(sorted(v, key=lambda x: x.runs[0]["run_id"])) for k, v in parts.items()}
    summ = {f"{s}/{c}": dict(rows=int(len(ds.y)), attack_frac=round(float(ds.y.mean()), 4),
                             runs=len(ds.runs)) for (s, c), ds in sorted(data.items())}
    json.dump(summ, open(os.path.join(OUT, "dataset_summary.json"), "w"), indent=1)
    return data


def _train_task(args):
    kind, k, c, seed = args
    data = _M["data"]
    if kind == "local":
        tr = data[("train", c)]
        return args, train_local(tr.X, tr.y, epochs=EPOCHS, seed=seed), None
    cs = _ctrl(k)
    if kind == "pooled":
        X = np.concatenate([data[("train", o)].X for o in cs])
        y = np.concatenate([data[("train", o)].y for o in cs])
        return args, train_local(X, y, epochs=EPOCHS, seed=seed), None
    m, comm, _ = train_federated([(data[("train", o)].X, data[("train", o)].y) for o in cs],
                                 rounds=FED_ROUNDS, mu=0.0, seed=seed)
    return args, m, comm


def train(data, workers):
    _M["data"] = data
    tasks = [("local", 0, c, s) for c in PROFILES for s in TRAIN_SEEDS]
    tasks += [(kind, k, "", s) for kind in ("fedavg", "pooled") for k in KS for s in TRAIN_SEEDS]
    models, comm = {}, {}
    with get_context("fork").Pool(workers) as p:
        for (kind, k, c, s), m, cm in p.imap_unordered(_train_task, tasks):
            models[(kind, k, c, s)] = m
            if cm is not None:
                comm[f"K{k}/seed{s}"] = cm
    # (training, K, controller, seed) -> model, threshold
    out = {}
    for k in KS:
        for c in _ctrl(k):
            v = data[("val", c)]
            for s in TRAIN_SEEDS:
                for kind in ("local", "fedavg", "pooled"):
                    m = models[(kind, 0, c, s)] if kind == "local" else models[(kind, k, "", s)]
                    out[(kind, k, c, s)] = (m, threshold_at_fpr(m.predict_proba(v.X[v.y == 0]), BUDGET))
    return out, comm


def offline(data, M):
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
    rows = []
    for c in PROFILES:
        D = data[("test_off", c)]
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben = np.array([x is None for x in var]) & (D.y == 0)
        cache = {}
        for (kind, k, cc, s), (m, tau) in M.items():
            if cc != c:
                continue
            key = (id(m),)
            if key not in cache:
                cache[key] = m.predict_proba(D.X)
            p = cache[key]
            for v in VARIANTS:
                mask = (var == v) | ben
                yt, pv = D.y[mask], p[mask]
                yp = (pv >= tau).astype(int)
                rows.append(dict(K=k, controller=c, training=kind, train_seed=s, variant=v,
                                 exposure=exposure(c, v, k), auc=roc_auc_score(yt, pv),
                                 accuracy=float((yp == yt).mean()),
                                 precision=precision_score(yt, yp, zero_division=0),
                                 recall=recall_score(yt, yp, zero_division=0),
                                 f1=f1_score(yt, yp, zero_division=0),
                                 fpr=float(((yp == 1) & (yt == 0)).sum() / max((yt == 0).sum(), 1))))
    return rows


def _episode(args):
    kind, k, c, s, v, seed = args
    prof, idx = PROFILES[c]
    tr = assign_ports(build_traffic(prof, idx, VARIANTS[v], seed, ONLINE_CFG.duration,
                                    ONLINE_CFG.attack_start), "dedicated")
    if kind == "none":
        dfn = Defense()
    else:
        m, tau = _M["models"][(kind, k, c, s)]
        dfn = DualGuard(m, tau, **_M["pol"])
    r = run_episode(tr, ONLINE_CFG, dfn, record_ts=False).summary
    return dict(K=k, controller=c, training=kind, train_seed=s, variant=v,
                exposure=exposure(c, v, k) if k else "", seed=seed,
                harmed=100 * r["benign_flows_harmed_frac"], attack_demotes=r["attack_demotes"],
                benign_demotes=r["benign_demotes"])


def online(M, workers):
    sel = json.load(open("results/v21/selected.json"))["selected"]
    _M.update(models=M, pol=v21._policy(sel))
    tasks = [("none", 0, c, 0, v, sd) for c in PROFILES for v in VARIANTS for sd in ONLINE_SEEDS]
    # Local models do not depend on K: run them once per controller (stored under K = 0).
    tasks += [("local", 0, c, s, v, sd) for c in PROFILES for s in TRAIN_SEEDS
              for v in VARIANTS for sd in ONLINE_SEEDS]
    tasks += [(kind, k, c, s, v, sd) for kind in ("fedavg", "pooled") for k in KS
              for c in _ctrl(k) for s in TRAIN_SEEDS for v in VARIANTS for sd in ONLINE_SEEDS]
    for c in PROFILES:                        # K = 0 key for the local models
        for s in TRAIN_SEEDS:
            M[("local", 0, c, s)] = M[("local", 9, c, s)]
    print(f"[online] {len(tasks)} episodes", flush=True)
    with get_context("fork").Pool(workers) as p:
        return p.map(_episode, tasks, chunksize=4)


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data = collect(a.workers)
    print(f"[collect] {time.time() - t0:.0f} s", flush=True)
    M, comm = train(data, a.workers)
    print(f"[train] {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(offline(data, M)).to_csv(os.path.join(OUT, "offline.csv"), index=False)
    print(f"[offline] {time.time() - t0:.0f} s", flush=True)
    del data
    _M.pop("data", None)
    pd.DataFrame(online(M, a.workers)).to_csv(os.path.join(OUT, "online.csv"), index=False)
    json.dump(dict(exposure=EXPOSURE, profiles={c: p.name for c, (p, _) in PROFILES.items()},
                   fedavg_comm=comm, total_seconds=round(time.time() - t0)),
              open(os.path.join(OUT, "train_info.json"), "w"), indent=1, default=str)
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
