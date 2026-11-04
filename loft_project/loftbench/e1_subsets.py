"""Which tree families does the federated ensemble need? Every subset of RF, CatBoost and
LightGBM, each family federated by model sharing (mean of the controllers' local models, as in
E1), combined by soft voting or by a local stacker (logistic regression on the members' logits,
fitted on one half of the controller's validation data; tau at the 1 % benign budget on the
other half). Same offline test as E1. Also: how often the members disagree.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e1_subsets

Writes results/e1_subsets/{offline.csv, table.csv, disagree.csv}.
"""
import itertools
import os
import pickle
import time

import numpy as np
import pandas as pd

from . import ml_compare as M
from .config import DOMAINS
from .models import SkWrap, threshold_at_fpr

OUT = "results/e1_subsets"
FAMS = ("rf", "cb", "lgb")


def _make(fam):
    if fam == "rf":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=0)
    if fam == "cb":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=300, depth=6, verbose=0, random_seed=0, thread_count=4)
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=200, num_leaves=31, random_state=0, n_jobs=4, verbose=-1)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class Stack:
    """Local stacker over the members' federated probabilities."""

    def __init__(self, members, X, y):
        from sklearn.linear_model import LogisticRegression
        self.members = members
        self.lr = LogisticRegression(C=1.0, max_iter=1000).fit(self._z(X), y)

    def _z(self, X):
        return np.column_stack([_logit(m.predict_proba(X)) for m in self.members])

    def predict_proba(self, X):
        return self.lr.predict_proba(self._z(X))[:, 1]


def main():
    os.makedirs(OUT, exist_ok=True)
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tr = {d: data[("train", d)] for d in DOMAINS}
    fed, info = {}, {}
    for fam in FAMS:
        t0 = time.time()
        local = {d: SkWrap(_make(fam).fit(tr[d].X, tr[d].y)) for d in DOMAINS}
        for m in local.values():
            if hasattr(m.m, "n_jobs"):
                m.m.n_jobs = 1
        fed[fam] = M.Mean(list(local.values()))
        info[fam] = dict(train_s=round(time.time() - t0, 1), bytes=len(pickle.dumps(local["D1"].m)))
        print(f"  trained {fam} {info[fam]}", flush=True)
    mlp = pickle.load(open("results/v21/models.pkl", "rb"))[0]["fedavg"]
    models, taus = {}, {}
    rng = np.random.default_rng(0)
    for d in DOMAINS:
        v = data[("val", d)]
        half = rng.random(len(v.y)) < 0.5
        A, B = half, ~half
        models[("mlp", "single", d)] = mlp
        for k in range(1, 4):
            for sub in itertools.combinations(FAMS, k):
                name = "+".join(sub)
                ms = [fed[f] for f in sub]
                models[(name, "vote", d)] = M.Mean(ms) if k > 1 else ms[0]
                if k > 1:
                    models[(name, "stack", d)] = Stack(ms, v.X[A], v.y[A])
        for key in [k for k in models if k[2] == d]:
            vb = v.X[B][v.y[B] == 0] if key[1] == "stack" else v.X[v.y == 0]
            taus[key] = threshold_at_fpr(models[key].predict_proba(vb), M.BUDGET)
    rows = pd.DataFrame(M.offline(data, models, taus))
    rows.to_csv(os.path.join(OUT, "offline.csv"), index=False)
    cols = ["f1", "fpr", "fnr", "mcc", "auc"]
    tab = (rows.groupby(["model", "training", "exposure"])[cols].mean() * 100).round(2)
    tab.to_csv(os.path.join(OUT, "table.csv"))
    # Disagreement on the offline test: members' decisions at their own taus.
    dis = []
    for d in DOMAINS:
        D = data[("test_off", d)]
        dec = {f: fed[f].predict_proba(D.X) >= taus[(f, "vote", d)] for f in FAMS}
        for y, lab in ((0, "benign"), (1, "attack")):
            msk = D.y == y
            votes = np.sum([dec[f][msk] for f in FAMS], axis=0)
            dis.append(dict(domain=d, label=lab, n=int(msk.sum()),
                            none=float((votes == 0).mean()), some=float(((votes > 0) & (votes < 3)).mean()),
                            all=float((votes == 3).mean())))
    dis = pd.DataFrame(dis)
    dis.to_csv(os.path.join(OUT, "disagree.csv"), index=False)
    pd.set_option("display.width", 200)
    piv = tab.reset_index().pivot_table(index=["model", "training"], columns="exposure", values=["f1", "fpr"])
    print(piv.round(2).to_string())
    print(dis.groupby("label")[["none", "some", "all"]].mean().round(4).to_string())
    print(info)


if __name__ == "__main__":
    main()
