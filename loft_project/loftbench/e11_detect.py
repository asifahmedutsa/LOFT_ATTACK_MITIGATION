"""E11: same-data detection benchmark. Ensguard's detector against the per-rule detectors of the
related papers, all scored on the same offline test split (results/v2/datasets.pkl, test_off) and
grouped by exposure as in E1 (attack seen by this controller, seen only by another, seen by none).

Detectors (each trained on the same v2 training rows, one model per controller D1-D3):
  ensguard      RF 50/12 + CatBoost, model sharing (results/e3_ens/models.pkl), federated only
  fl-dualguard  the frozen v2.1 MLP (FedProx), federated only
  ftmaster      XGBoost on FTMaster's six rule features      (results/e2_baselines/models.pkl)
  ftop          Random Forest on FTOP's four rule features    (results/e2_baselines/models.pkl)
  flora         CatBoost on FloRa's eight flow features       (results/e2_baselines/models.pkl)
  dms-btt       CatBoost on DMS-BTT's (Numb, PIT, Sizep)      (results/v2/models.pkl)
The baselines are scored as their papers deploy them (local: each controller's own model) and,
for a fair test of the ensemble itself, federated the same way as ensguard (mean of the three
controllers' probabilities).

Operating points: "paper" (0.5 for the baselines, the deployed tau for ensguard and
fl-dualguard), and tau at a 1 %, 0.1 % and 0.01 % benign rate on the controller's validation
data. Metrics per controller and attack: accuracy, precision, recall, F1, FPR, MCC, ROC-AUC,
PR-AUC (average precision); the tables give mean and std over the (controller, attack) cells.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e11_detect

Writes results/e11_detect/{cells.csv, table.csv, table_main.csv}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pickle
import time

import numpy as np
import pandas as pd

from .baselines import flora_rule_features, ftmaster_rule_features, ftop_rule_features
from .config import DOMAINS, UNSEEN_VARIANTS, EXPOSURE, VARIANTS
from .models import threshold_at_fpr

OUT = "results/e11_detect"
OPS = {"fpr1": 0.01, "fpr0.1": 0.001, "fpr0.01": 0.0001}
RULE = {"ftmaster": ftmaster_rule_features, "ftop": ftop_rule_features, "flora": flora_rule_features}


def _p1(m, Z):
    p = m.predict_proba(Z)
    return p[:, 1] if np.ndim(p) == 2 else p


def _exposure(d, v):
    if v in UNSEEN_VARIANTS:
        return "unseen-all"
    return "seen-local" if v in EXPOSURE[d] else "seen-remote"


def _detectors():
    """name -> (training, {d: scorer(ds) -> P(attack)}, {d: paper threshold})."""
    from . import e2_baselines as E2
    from . import v21
    E2._load()
    base = pickle.load(open("results/e2_baselines/models.pkl", "rb"))
    v2m = pickle.load(open("results/v2/models.pkl", "rb"))[0]
    ens = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"]
    det = {}
    # Ensguard's deployed tau is the 0.1 % benign budget on validation data (ens_config.json),
    # the fpr0.1 operating point; main() fills it in as "paper".
    det["ensguard"] = ("federated", {d: (lambda ds: ens.predict_proba(ds.X)) for d in DOMAINS}, "fpr0.1")
    dg = {d: v21._make("v2.1", d, None) for d in DOMAINS}

    def _dg(d):
        g = dg[d]
        return lambda ds: _p1(g.model, ds.X if g.feature_idx is None else ds.X[:, g.feature_idx])
    det["fl-dualguard"] = ("federated", {d: _dg(d) for d in DOMAINS}, {d: dg[d].tau for d in DOMAINS})

    def _rule(fam, d):
        m = base[f"{fam}_rule/{d}"]
        f = RULE[fam]
        return lambda ds: _p1(m, f(ds.X))

    def _dms(d):
        m = v2m[f"dms_flow/{d}"]
        return lambda ds: _p1(m, ds.dms)
    for fam in ("ftmaster", "ftop", "flora", "dms-btt"):
        local = {d: (_dms(d) if fam == "dms-btt" else _rule(fam, d)) for d in DOMAINS}
        det[fam] = ("local", local, {d: 0.5 for d in DOMAINS})
        det[fam + "@fed"] = ("federated", {d: (lambda ds, L=local: np.mean([L[x](ds) for x in DOMAINS], axis=0))
                                           for d in DOMAINS}, {d: 0.5 for d in DOMAINS})
    return det


def _metrics(yt, pv, tau):
    from sklearn.metrics import average_precision_score, matthews_corrcoef, roc_auc_score
    yp = (pv >= tau).astype(int)
    tp, fp = int(((yp == 1) & (yt == 1)).sum()), int(((yp == 1) & (yt == 0)).sum())
    fn, tn = int(((yp == 0) & (yt == 1)).sum()), int(((yp == 0) & (yt == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return dict(accuracy=(tp + tn) / len(yt), precision=prec, recall=rec,
                f1=2 * prec * rec / max(prec + rec, 1e-12), fpr=fp / max(fp + tn, 1),
                mcc=float(matthews_corrcoef(yt, yp)), auc=roc_auc_score(yt, pv),
                pr_auc=average_precision_score(yt, pv))


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    det = _detectors()
    rows = []
    for d in DOMAINS:
        D, V = data[("test_off", d)], data[("val", d)]
        Vb = V.subset(V.y == 0)
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben_run = np.array([x is None for x in var])
        for name, (how, score, paper_tau) in det.items():
            p = score[d](D)
            vb = score[d](Vb)
            taus = {op: threshold_at_fpr(vb, f) for op, f in OPS.items()}
            taus["paper"] = taus[paper_tau] if isinstance(paper_tau, str) else paper_tau[d]
            for v in VARIANTS:
                mask = (var == v) | (ben_run & (D.y == 0))
                for op, tau in taus.items():
                    rows.append(dict(detector=name, training=how, op=op, domain=d, variant=v,
                                     exposure=_exposure(d, v), tau=tau, **_metrics(D.y[mask], p[mask], tau)))
            print(f"  {d} {name} {time.time() - t0:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "cells.csv"), index=False)
    cols = ["accuracy", "precision", "recall", "f1", "fpr", "mcc", "auc", "pr_auc"]
    g = df.groupby(["detector", "training", "op", "exposure"])[cols]
    tab = (g.mean() * 100).round(2).join((g.std() * 100).round(2), rsuffix="_std")
    tab.to_csv(os.path.join(OUT, "table.csv"))
    main_tab = tab.reset_index()
    main_tab = main_tab[main_tab.op.isin(["paper", "fpr0.1"])][
        ["detector", "op", "exposure", "accuracy", "precision", "recall", "f1", "fpr", "auc", "pr_auc"]]
    main_tab.to_csv(os.path.join(OUT, "table_main.csv"), index=False)
    pd.set_option("display.width", 220)
    print(main_tab.to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
