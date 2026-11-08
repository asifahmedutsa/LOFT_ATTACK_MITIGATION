"""Exploratory, not preregistered: offline metrics of the reimplemented baselines' rule classifiers
on the testbed T1B test rows (seeds 4176-4178), beside FEVER's detector, as in results/tbfl/report.md.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_baselines   # writes results/tbfl/baselines_offline.*

Each baseline's per-rule classifier with its own features and model (loftbench.baselines, ftodefender),
trained three ways: on simulator T1A rows (the models the testbed runs so far used), on C3's testbed
rows (T1A, seeds 4170-4172, as in its paper: one controller, one trace) and on C1-C3's testbed rows
pooled (equal data with FEVER). Thresholds: the papers' 0.5, and FEVER's rule (0.1 % of the T1A
benign rows of seeds 4173-4175). Table-state detectors (FTMaster, FTOP, DMS-BTT state models) are not
scored here: their labels are per poll, not per entry.
"""
import json
import pickle
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .baselines import flora_rule_features, ftmaster_rule_features, ftod_rule_features, ftop_rule_features
from .data import Dataset
from .models import threshold_at_fpr
from .realfl import ALL, BUDGET, Booster
from .tbfl import CTRL, OUT, TEST, VAL, train_rows

EXP = "results/v21/exported"
FEAT = {"FTMaster": lambda d: ftmaster_rule_features(d.X), "FTOP": lambda d: ftop_rule_features(d.X),
        "FloRa": lambda d: flora_rule_features(d.X), "DMS-BTT": lambda d: d.dms,
        "FTODefender": lambda d: ftod_rule_features(d.X)}


def p1(m, Z):
    p = np.asarray(m.predict_proba(Z))
    return p[:, 1] if p.ndim == 2 else p


class GbmLR:
    """FTODefender's rule classifier: LightGBM leaves, one-hot, logistic regression."""
    def __init__(self, Z, y):
        import lightgbm as lgb
        from sklearn.linear_model import LogisticRegression
        from .lgbjson import leaves, onehot
        self.leaves, self.onehot = leaves, onehot
        self.gbm = lgb.LGBMClassifier(n_estimators=100, random_state=0, n_jobs=4, verbose=-1).fit(Z, y)
        self.width = int(max(t["num_leaves"] for t in self.gbm.booster_.dump_model()["tree_info"]))
        self.lr = LogisticRegression(max_iter=2000).fit(self._h(Z), y)

    def _h(self, Z):
        return self.onehot(self.leaves(self.gbm.booster_, Z), self.width)

    def predict_proba(self, Z):
        return self.lr.predict_proba(self._h(Z))


def fit(name, d):
    """The baseline's model with the settings of loftbench.v5 / ftodefender."""
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    Z, y = FEAT[name](d), d.y
    if name == "FTMaster":
        return XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4, random_state=0).fit(Z, y)
    if name == "FTOP":
        return RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=0).fit(Z, y)
    if name in ("FloRa", "DMS-BTT"):
        return CatBoostClassifier(iterations=300, random_seed=0, verbose=False, thread_count=4).fit(Z, y)
    return GbmLR(Z, y)


def sim_model(n):
    """The model the testbed runs so far used (simulator T1A rows, loftbench.v5)."""
    if n == "FTODefender":     # never exported for T1B: trained as loftbench.ftodefender would, on the same rows
        from . import v5
        return fit(n, v5._t1a()[0])
    a = pickle.load(open("results/v5/baselines_t1a.pkl" if n in ("FTMaster", "DMS-BTT") else
                         "results/v5/baselines2_t1a.pkl", "rb"))
    return a[{"FTMaster": "ftmaster_rule", "DMS-BTT": "dms_flow", "FTOP": "ftop_rule", "FloRa": "flora_rule"}[n]]


def metrics(p, y, tau):
    f = p >= tau
    tp, fp = int((f & (y == 1)).sum()), int((f & (y == 0)).sum())
    fn, tn = int((~f & (y == 1)).sum()), int((~f & (y == 0)).sum())
    pr, rc = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    den = np.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return dict(accuracy=100 * (tp + tn) / max(len(y), 1), precision=100 * pr, recall=100 * rc,
                f1=100 * 2 * pr * rc / max(pr + rc, 1e-12), fnr=100 * fn / max(tp + fn, 1),
                mcc=(tp * tn - fp * fn) / den if den else 0.0)


def main():
    # One model at a time, scored and freed, rows written as they come (the first version ran out of
    # memory holding every model and every copy of the rows on this 8 GB machine).
    import gc
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    cal = Dataset.concat([runs[("T1A", None, s)] for s in VAL])
    b = cal.y == 0
    cal = SimpleNamespace(X=cal.X[b], dms=cal.dms[b], y=cal.y[b])
    keys = [(v, s) for v in [None] + ALL for s in TEST]
    alla = Dataset.concat([runs[("T1B", v, s)] for v, s in keys])
    owner = np.concatenate([np.full(len(runs[("T1B", v, s)].y), i) for i, (v, s) in enumerate(keys)])
    ben = np.isin(owner, [i for i, (v, _) in enumerate(keys) if v is None])
    per = {v: np.isin(owner, [i for i, (w, _) in enumerate(keys) if w == v]) & (alla.y == 1) for v in ALL}
    del owner
    assert ben.sum() > 0 and all(m.sum() > 0 for m in per.values()), "run ids do not match"
    train = {"testbed, C3 only": train_rows(runs, "C3"),
             "testbed, C1-C3 pooled": Dataset.concat([train_rows(runs, c) for c in CTRL])}
    info = dict(test_rows=int(len(alla.y)), benign_test_rows=int(ben.sum()), cal_rows=int(len(cal.y)),
                **{f"{k} rows": int(len(d.y)) for k, d in train.items()})
    del runs
    gc.collect()
    json.dump(info, open(f"{OUT}/baselines_offline_info.json", "w"), indent=1)
    rows = []

    def score(name, tr, pf):
        pa, pc = pf(alla), pf(cal)
        for rule in ("0.5 (paper)", "0.1 % of T1A benign"):
            if name.startswith("FEVER") and rule.startswith("0.5"):
                continue
            tau = 0.5 if rule.startswith("0.5") else float(threshold_at_fpr(pc, BUDGET))
            r = dict(method=name, training=tr, threshold=rule, tau=tau,
                     false_alarms=100 * float((pa[ben] >= tau).mean()))
            r.update(metrics(pa, alla.y, tau))
            for v in ALL:
                r[f"recall {v}"] = 100 * float((pa[per[v]] >= tau).mean())
            rows.append(r)
            pd.DataFrame(rows).round(4).to_csv(f"{OUT}/baselines_offline.csv", index=False)
            print(name, tr, rule, round(r["false_alarms"], 2), round(r["recall"], 2), flush=True)

    fever = Booster(f"{OUT}/fedxgb_hist.json")
    score("FEVER (lossless federated XGBoost)", "testbed, C1-C3 federated", lambda d: p1(fever, d.X))
    for n in FEAT:
        m = sim_model(n)
        score(n, "simulator T1A rows", lambda d, m=m, n=n: p1(m, FEAT[n](d)))
        del m
        gc.collect()
        for tr, d in train.items():
            m = fit(n, d)
            score(n, tr, lambda d, m=m, n=n: p1(m, FEAT[n](d)))
            del m
            gc.collect()


if __name__ == "__main__":
    main()
