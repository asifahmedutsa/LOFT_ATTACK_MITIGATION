"""E1 (docs/other_papers_run_plan.md): offline classification table in the related papers'
format, on the saved v2 datasets (D1-D3, train / val / test_off runs).

Per-rule task (what SFTO-Guard, FTMaster, FTOP, FloRa and DMS-BTT report): 8 classifier
families on our 17 features, each trained local (one controller), federated and pooled (all
raw data, the upper bound). The MLP is federated by FedAvg; the other families cannot be
weight-averaged, so their federated version averages the three local models' probabilities.
Two operating points: the papers' default (score >= 0.5) and ours (tau at 1 % of benign
validation rows, per controller). Metrics per attack variant and mixed: accuracy,
precision, recall, F1, FPR, FNR, MCC, AUC; plus per-rule inference time.

Table-state task (DMS-BTT's three states from FN and APIT): pooled classifiers, accuracy and
attack detection rate, as DMS-BTT reports them.

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e1_offline [--seeds 0,1,2]

Seed 0 uses the deployed v2.1 MLPs; other seeds retrain them. Writes results/e1_offline/
{rule.csv, state.csv, timing.csv, summary_rule.csv, summary_state.csv}.
"""
import argparse
import os
import pickle
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, matthews_corrcoef, precision_score,
                             recall_score, roc_auc_score)

from .config import DOMAINS, EXPOSURE, UNSEEN_VARIANTS, VARIANTS
from .models import threshold_at_fpr, train_federated, train_local

OUT = "results/e1_offline"
BUDGET = 0.01
SUB = 60000          # training rows for KNN and SVM (both scale badly with rows)
FAMILIES = ["mlp", "rf", "xgboost", "lightgbm", "catboost", "knn", "svm", "lr"]


class Prob:
    """Uniform predict_proba(X) -> P(attack) over the sklearn-style families."""

    def __init__(self, m, decision=False):
        self.m, self.decision = m, decision

    def predict_proba(self, X):
        if self.decision:                         # linear SVM: sigmoid of the margin
            return 1.0 / (1.0 + np.exp(-self.m.decision_function(X)))
        return self.m.predict_proba(X)[:, 1]


def _make(fam, seed):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import LinearSVC
    if fam == "rf":
        return RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=seed), False
    if fam == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, n_jobs=4,
                             random_state=seed, tree_method="hist"), False
    if fam == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(n_estimators=300, learning_rate=0.1, n_jobs=4, random_state=seed,
                              verbose=-1), False
    if fam == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=300, random_seed=seed, verbose=False,
                                  thread_count=4), False
    if fam == "knn":
        return make_pipeline(StandardScaler(), KNeighborsClassifier(15, n_jobs=4)), False
    if fam == "svm":
        return make_pipeline(StandardScaler(), LinearSVC(C=1.0, random_state=seed)), True
    if fam == "lr":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)), False
    raise ValueError(fam)


def _fit(fam, X, y, seed):
    m, dec = _make(fam, seed)
    if fam in ("knn", "svm") and len(y) > SUB:
        i = np.random.default_rng(seed).choice(len(y), SUB, replace=False)
        X, y = X[i], y[i]
    return Prob(m.fit(X, y), dec)


def _single_thread(m):
    """Per-rule timing on one core, as a controller would serve it (CatBoost keeps its own
    thread setting)."""
    if not isinstance(m, Prob):
        return
    for est in [m.m] + list(getattr(m.m, "named_steps", {}).values()):
        if hasattr(est, "n_jobs"):
            est.n_jobs = 1


def train(data, fam, seed):
    tr = {d: data[("train", d)] for d in DOMAINS}
    allX = np.concatenate([tr[d].X for d in DOMAINS])
    ally = np.concatenate([tr[d].y for d in DOMAINS])
    if fam == "mlp":
        if seed == 0:
            mlp = pickle.load(open("results/v21/models.pkl", "rb"))[0]
            local = {d: mlp[f"local/{d}"] for d in DOMAINS}
            return local, mlp["fedavg"], mlp["pooled"]
        local = {d: train_local(tr[d].X, tr[d].y, epochs=30, seed=seed) for d in DOMAINS}
        fed = train_federated([(tr[d].X, tr[d].y) for d in DOMAINS], rounds=30, mu=0.0, seed=seed)[0]
        return local, fed, train_local(allX, ally, epochs=30, seed=seed)
    local = {d: _fit(fam, tr[d].X, tr[d].y, seed) for d in DOMAINS}
    return local, None, _fit(fam, allX, ally, seed)


def _metrics(yt, p, tau):
    yp = (p >= tau).astype(int)
    neg, pos = max((yt == 0).sum(), 1), max((yt == 1).sum(), 1)
    return dict(accuracy=accuracy_score(yt, yp), precision=precision_score(yt, yp, zero_division=0),
                recall=recall_score(yt, yp, zero_division=0), f1=f1_score(yt, yp, zero_division=0),
                fpr=((yp == 1) & (yt == 0)).sum() / neg, fnr=((yp == 0) & (yt == 1)).sum() / pos,
                mcc=matthews_corrcoef(yt, yp))


def _exposure(d, v):
    if v in UNSEEN_VARIANTS:
        return "unseen-all"
    return "seen-local" if v in EXPOSURE[d] else "seen-remote"


def evaluate(data, fam, seed, local, fed, pooled):
    """Scores every model on every controller's val and test_off rows; local-model scores are
    cached and averaged for the tree families' federated version."""
    cache = {}

    def score(split, d, key, m):
        k = (split, d, key)
        if k not in cache:
            cache[k] = m.predict_proba(data[(split, d)].X)
        return cache[k]

    rows = []
    for d in DOMAINS:
        D = data[("test_off", d)]
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben_run = np.array([x is None for x in var])
        for how in ("local", "federated", "pooled"):
            if how == "local":
                pv, pt = score("val", d, f"local/{d}", local[d]), score("test_off", d, f"local/{d}", local[d])
            elif how == "pooled":
                pv, pt = score("val", d, "pooled", pooled), score("test_off", d, "pooled", pooled)
            elif fed is not None:
                pv, pt = score("val", d, "fed", fed), score("test_off", d, "fed", fed)
            else:
                pv = np.mean([score("val", d, f"local/{o}", local[o]) for o in DOMAINS], axis=0)
                pt = np.mean([score("test_off", d, f"local/{o}", local[o]) for o in DOMAINS], axis=0)
            vb = data[("val", d)].y == 0
            taus = {"default": 0.5, "budget": threshold_at_fpr(pv[vb], BUDGET)}
            for v in list(VARIANTS) + ["mixed"]:
                mask = np.ones(len(D.y), bool) if v == "mixed" else (var == v) | (ben_run & (D.y == 0))
                yt, p = D.y[mask], pt[mask]
                auc = roc_auc_score(yt, p)
                for op, tau in taus.items():
                    rows.append(dict(model=fam, training=how, train_seed=seed, domain=d, variant=v,
                                     exposure="mixed" if v == "mixed" else _exposure(d, v),
                                     op=op, tau=tau, auc=auc, **_metrics(yt, p, tau)))
    return rows


def timing(data, fam, local, fed, pooled):
    X = data[("test_off", "D1")].X[:20000]
    out = []
    for how, m in (("local", local["D1"]), ("pooled", pooled)):
        _single_thread(m)
        m.predict_proba(X[:100])
        t0 = time.perf_counter()
        m.predict_proba(X)
        out.append(dict(model=fam, training=how,
                        us_per_rule=1e6 * (time.perf_counter() - t0) / len(X),
                        model_bytes=len(pickle.dumps(getattr(m, "m", m)))))
    return out


def state_task(data, seed):
    """DMS-BTT's table-state classifier: states 0 / 1 / 2 from (FN, APIT), pooled training."""
    from catboost import CatBoostClassifier
    from lightgbm import LGBMClassifier
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    tr = np.concatenate([data[("train", d)].state for d in DOMAINS])
    makers = {"catboost": lambda: CatBoostClassifier(iterations=300, loss_function="MultiClass",
                                                     random_seed=seed, verbose=False, thread_count=4),
              "rf": lambda: RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=seed),
              "xgboost": lambda: XGBClassifier(n_estimators=300, max_depth=6, n_jobs=4, random_state=seed),
              "lightgbm": lambda: LGBMClassifier(n_estimators=300, n_jobs=4, random_state=seed, verbose=-1)}
    rows = []
    for fam, mk in makers.items():
        m = mk().fit(tr[:, :2], tr[:, 2].astype(int))
        for d in DOMAINS:
            te = data[("test_off", d)].state
            yt = te[:, 2].astype(int)
            yp = np.asarray(m.predict(te[:, :2])).ravel().astype(int)
            att = yt > 0
            rows.append(dict(model=fam, train_seed=seed, domain=d, polls=len(yt),
                             accuracy=float((yp == yt).mean()),
                             attack_detection_rate=float((yp[att] > 0).mean()),
                             false_alarm_rate=float((yp[~att] > 0).mean())))
    return rows


def summarize(rule, state):
    keys = ["model", "training", "op", "exposure"]
    m = ["accuracy", "precision", "recall", "f1", "fpr", "fnr", "mcc", "auc"]
    per_seed = rule.groupby(keys + ["train_seed"])[m].mean() * 100
    s = per_seed.groupby(keys).agg(["mean", "std"]).round(2)
    s.columns = [f"{a}_{b}" for a, b in s.columns]
    st = (state.groupby(["model", "train_seed"])[["accuracy", "attack_detection_rate",
                                                  "false_alarm_rate"]].mean() * 100)
    st = st.groupby("model").agg(["mean", "std"]).round(2)
    st.columns = [f"{a}_{b}" for a, b in st.columns]
    return s.reset_index(), st.reset_index()


def _load(name):
    p = os.path.join(OUT, name)
    return pd.read_csv(p).to_dict("records") if os.path.exists(p) else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--knn-seeds", default="0", help="KNN is slow (about 36 min per seed)")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    print(f"[data] {time.time() - t0:.0f} s", flush=True)
    # Resumable: (family, seed) pairs, timings and state seeds already on disk are kept.
    rule, tim, state = _load("rule.csv"), _load("timing.csv"), _load("state.csv")
    done = {(r["model"], r["train_seed"]) for r in rule}
    knn_seeds = set(map(int, a.knn_seeds.split(",")))
    for seed in map(int, a.seeds.split(",")):
        for fam in FAMILIES:
            need_eval = (fam, seed) not in done and (fam != "knn" or seed in knn_seeds)
            need_time = seed == 0 and fam not in {r["model"] for r in tim}
            if not (need_eval or need_time):
                continue
            t1 = time.time()
            local, fed, pooled = train(data, fam, seed)
            if need_eval:
                rule += evaluate(data, fam, seed, local, fed, pooled)
                pd.DataFrame(rule).to_csv(os.path.join(OUT, "rule.csv"), index=False)
            if need_time:
                tim += timing(data, fam, local, fed, pooled)
                pd.DataFrame(tim).to_csv(os.path.join(OUT, "timing.csv"), index=False)
            print(f"[seed {seed}] {fam} {time.time() - t1:.0f} s", flush=True)
        if seed not in {r["train_seed"] for r in state}:
            state += state_task(data, seed)
            pd.DataFrame(state).to_csv(os.path.join(OUT, "state.csv"), index=False)
        print(f"[seed {seed}] state task done, {time.time() - t0:.0f} s", flush=True)
    rule, state = pd.DataFrame(rule), pd.DataFrame(state)
    s, st = summarize(rule, state)
    s.to_csv(os.path.join(OUT, "summary_rule.csv"), index=False)
    st.to_csv(os.path.join(OUT, "summary_state.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s[s.exposure == "mixed"].to_string(index=False))
    print(st.to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
