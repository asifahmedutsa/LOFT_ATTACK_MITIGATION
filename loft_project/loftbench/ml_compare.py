"""Short test: does the detector's model family change the federated-learning outcome?

The deployed MLP (FedAvg) against Random Forest and histogram gradient boosting (the model
families of FTOP/FTMaster and SFTO-Guard/FTODefender). Each family is trained three ways on
the saved v2 datasets: local (one controller's data), federated and pooled (all raw data, the
upper bound). Trees cannot be weight-averaged, so their federated version is the standard
alternative: each controller trains locally and shares its model, and a controller averages
the three models' probabilities. Thresholds are calibrated per controller at the 1 % benign
budget on local validation data, as for v2.1.

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.ml_compare [--seed S]

Seed 0 uses the deployed v2.1 MLPs; another seed retrains the MLPs (local, FedAvg, pooled) and
the trees with that seed. Writes results/ml_compare/{offline.csv, online.csv, train_info.json}
(seed 0) or results/ml_compare/seed<S>/.
"""
import json
import os
import pickle
import time
from multiprocessing import get_context

import numpy as np

from . import v21
from .config import DOMAINS, EXPOSURE, UNSEEN_VARIANTS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DualGuard
from .models import SkWrap, threshold_at_fpr, train_federated, train_local
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/ml_compare"
BUDGET = 0.01
# Online cells: per controller, the first-listed exposure of each other controller and A6.
CELLS = {"D1": ["A2", "A3", "A6"], "D2": ["A1", "A3", "A6"], "D3": ["A1", "A2", "A6"]}
SEEDS = [8000, 8001, 8002]
_M = {}
SEED = 0


class Mean:
    """Federated tree models: average of the controllers' local models' probabilities."""

    def __init__(self, ms):
        self.ms = ms

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.ms], axis=0)


def _rf():
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=SEED)


def _hgb():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=200, random_state=SEED)


def train(data):
    models, info = {}, {}
    tr = {d: data[("train", d)] for d in DOMAINS}
    allX = np.concatenate([tr[d].X for d in DOMAINS])
    ally = np.concatenate([tr[d].y for d in DOMAINS])
    if SEED == 0:
        mlp = pickle.load(open("results/v21/models.pkl", "rb"))[0]
    else:
        mlp = {f"local/{d}": train_local(tr[d].X, tr[d].y, epochs=30, seed=SEED) for d in DOMAINS}
        mlp["pooled"] = train_local(allX, ally, epochs=30, seed=SEED)
        mlp["fedavg"] = train_federated([(tr[d].X, tr[d].y) for d in DOMAINS], rounds=30,
                                        mu=0.0, seed=SEED)[0]
        print("  trained mlp", flush=True)
    for d in DOMAINS:
        models[("mlp", "local", d)] = mlp[f"local/{d}"]
        models[("mlp", "federated", d)] = mlp["fedavg"]
        models[("mlp", "pooled", d)] = mlp["pooled"]
    for fam, make in (("rf", _rf), ("hgb", _hgb)):
        t0 = time.time()
        local = {d: SkWrap(make().fit(tr[d].X, tr[d].y)) for d in DOMAINS}
        fed = Mean(list(local.values()))
        pooled = SkWrap(make().fit(allX, ally))
        for m in local.values():                 # one core per process at serving time
            if hasattr(m.m, "n_jobs"):
                m.m.n_jobs = 1
        if hasattr(pooled.m, "n_jobs"):
            pooled.m.n_jobs = 1
        for d in DOMAINS:
            models[(fam, "local", d)] = local[d]
            models[(fam, "federated", d)] = fed
            models[(fam, "pooled", d)] = pooled
        info[fam] = dict(train_seconds=round(time.time() - t0, 1),
                         model_bytes=len(pickle.dumps(local["D1"].m)))
        print(f"  trained {fam} in {info[fam]['train_seconds']} s", flush=True)
    info["mlp"] = dict(model_bytes=int(mlp["fedavg"].n_bytes()))
    taus = {}
    for k, m in models.items():
        v = data[("val", k[2])]
        taus[k] = threshold_at_fpr(m.predict_proba(v.X[v.y == 0]), BUDGET)
    return models, taus, info


def _exposure(d, v):
    if v in UNSEEN_VARIANTS:
        return "unseen-all"
    return "seen-local" if v in EXPOSURE[d] else "seen-remote"


def offline(data, models, taus):
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
    rows = []
    for d in DOMAINS:
        D = data[("test_off", d)]
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben_run = np.array([x is None for x in var])
        for (fam, how, dd), m in models.items():
            if dd != d:
                continue
            p = m.predict_proba(D.X)
            for v in VARIANTS:
                mask = (var == v) | (ben_run & (D.y == 0))
                yt, pv = D.y[mask], p[mask]
                yp = (pv >= taus[(fam, how, d)]).astype(int)
                rows.append(dict(model=fam, training=how, train_seed=SEED, domain=d, variant=v,
                                 exposure=_exposure(d, v), auc=roc_auc_score(yt, pv),
                                 accuracy=float((yp == yt).mean()),
                                 precision=precision_score(yt, yp, zero_division=0),
                                 recall=recall_score(yt, yp, zero_division=0),
                                 f1=f1_score(yt, yp, zero_division=0),
                                 fpr=float(((yp == 1) & (yt == 0)).sum() / max((yt == 0).sum(), 1))))
        print(f"  offline {d} done", flush=True)
    return rows


def _episode(args):
    fam, how, d, v, s = args
    models, taus, pol = _M["models"], _M["taus"], _M["pol"]
    dg = DualGuard(models[(fam, how, d)], taus[(fam, how, d)], **pol)
    cfg = SimConfig(duration=300.0)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v], s, cfg.duration,
                                    cfg.attack_start), "dedicated")
    r = run_episode(tr, cfg, dg, record_ts=False).summary
    return dict(model=fam, training=how, domain=d, variant=v, seed=s,
                train_seed=SEED, harmed=100 * r["benign_flows_harmed_frac"], attack_demotes=r["attack_demotes"],
                benign_demotes=r["benign_demotes"], decision_ms=1000 * r["decision_ms_mean"])


def main():
    import argparse
    import pandas as pd
    global OUT, SEED
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    SEED = ap.parse_args().seed
    if SEED:
        OUT = os.path.join(OUT, f"seed{SEED}")
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    print(f"[train] data loaded in {time.time() - t0:.0f} s", flush=True)
    models, taus, info = train(data)
    print("[offline]", flush=True)
    pd.DataFrame(offline(data, models, taus)).to_csv(os.path.join(OUT, "offline.csv"), index=False)
    del data
    sel = json.load(open("results/v21/selected.json"))["selected"]
    _M.update(models=models, taus=taus, pol=v21._policy(sel))
    tasks = [(f, h, d, v, s) for f in ("mlp", "rf", "hgb") for h in ("local", "federated")
             for d, vs in CELLS.items() for v in vs for s in SEEDS]
    print(f"[online] {len(tasks)} episodes", flush=True)
    with get_context("fork").Pool(4) as p:
        rows = p.map(_episode, tasks, chunksize=1)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "online.csv"), index=False)
    info["total_seconds"] = round(time.time() - t0)
    json.dump(info, open(os.path.join(OUT, "train_info.json"), "w"), indent=2)
    print(f"done in {info['total_seconds']} s", flush=True)


if __name__ == "__main__":
    main()
