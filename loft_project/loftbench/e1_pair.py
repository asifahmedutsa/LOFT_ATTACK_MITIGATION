"""RF + CatBoost, federated by model sharing: how small can the forest be, and how often do the
two members disagree? RF variants: E1's forest (100 trees, min_samples_leaf 5) and capped ones.
Each pair is combined by soft voting and by the local stacker of e1_subsets. Reports the
offline F1/FPR by exposure, the per-controller model size, scoring time per 10,000 entries,
and the share of benign and attack test flows flagged by neither, one or both members.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e1_pair

Writes results/e1_pair/{offline.csv, table.csv, disagree.csv, cost.csv}.
"""
import os
import pickle
import time

import numpy as np
import pandas as pd

from . import ml_compare as M
from .config import DOMAINS
from .e1_subsets import Stack, _make
from .models import SkWrap, threshold_at_fpr

OUT = "results/e1_pair"
RF = {"rf100": dict(n_estimators=100, min_samples_leaf=5),
      "rf50d12": dict(n_estimators=50, max_depth=12, min_samples_leaf=5),
      "rf30d10": dict(n_estimators=30, max_depth=10, min_samples_leaf=5)}


def _rf(kw):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_jobs=4, random_state=0, **kw)


def _fit(make, tr):
    local = {d: SkWrap(make().fit(tr[d].X, tr[d].y)) for d in DOMAINS}
    for m in local.values():
        if hasattr(m.m, "n_jobs"):
            m.m.n_jobs = 1
    return M.Mean(list(local.values())), len(pickle.dumps(local["D1"].m))


def _ms_per_10k(m, X):
    X = X[:10000]
    t0 = time.perf_counter()
    m.predict_proba(X)
    return 1000 * (time.perf_counter() - t0) * 10000 / len(X)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tr = {d: data[("train", d)] for d in DOMAINS}
    Xc = data[("test_off", "D1")].X
    fed, cost = {}, []
    for name, kw in [*RF.items(), ("cb", None)]:
        fed[name], size = _fit((lambda: _make("cb")) if kw is None else (lambda kw=kw: _rf(kw)), tr)
        cost.append(dict(model=name, bytes_per_controller=size,
                         ms_per_10k_entries=round(_ms_per_10k(fed[name], Xc), 1)))
        print(f"  trained {cost[-1]}", flush=True)
    models, taus = {}, {}
    rng = np.random.default_rng(0)
    for d in DOMAINS:
        v = data[("val", d)]
        A = rng.random(len(v.y)) < 0.5
        B = ~A
        models[("cb", "single", d)] = fed["cb"]
        for r in RF:
            models[(r, "single", d)] = fed[r]
            models[(f"{r}+cb", "vote", d)] = M.Mean([fed[r], fed["cb"]])
            models[(f"{r}+cb", "stack", d)] = Stack([fed[r], fed["cb"]], v.X[A], v.y[A])
        for key in [k for k in models if k[2] == d]:
            vb = v.X[B][v.y[B] == 0] if key[1] == "stack" else v.X[v.y == 0]
            taus[key] = threshold_at_fpr(models[key].predict_proba(vb), M.BUDGET)
    rows = pd.DataFrame(M.offline(data, models, taus))
    rows.to_csv(os.path.join(OUT, "offline.csv"), index=False)
    tab = (rows.groupby(["model", "training", "exposure"])[["f1", "fpr", "fnr", "auc"]].mean() * 100).round(2)
    tab.to_csv(os.path.join(OUT, "table.csv"))
    dis = []
    for d in DOMAINS:
        D = data[("test_off", d)]
        cb = fed["cb"].predict_proba(D.X) >= taus[("cb", "single", d)]
        for r in RF:
            rf = fed[r].predict_proba(D.X) >= taus[(r, "single", d)]
            for y, lab in ((0, "benign"), (1, "attack")):
                msk = D.y == y
                n = rf[msk].astype(int) + cb[msk].astype(int)
                dis.append(dict(rf=r, domain=d, label=lab, none=float((n == 0).mean()),
                                one=float((n == 1).mean()), both=float((n == 2).mean())))
    dis = pd.DataFrame(dis)
    dis.to_csv(os.path.join(OUT, "disagree.csv"), index=False)
    pd.DataFrame(cost).to_csv(os.path.join(OUT, "cost.csv"), index=False)
    pd.set_option("display.width", 200)
    print(tab.reset_index().pivot_table(index=["model", "training"], columns="exposure",
                                        values=["f1", "fpr"]).round(2).to_string())
    print((dis.groupby(["rf", "label"])[["none", "one", "both"]].mean() * 100).round(2).to_string())
    print(pd.DataFrame(cost).to_string(index=False))


if __name__ == "__main__":
    main()
