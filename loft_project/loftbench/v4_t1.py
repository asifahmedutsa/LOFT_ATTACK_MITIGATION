"""EnsGuard v4, phases 1-2 (docs/v4_plan.md): T1 joins the federation, then the offline check.

train  T1's local RF (50 trees, depth 12) and CatBoost on the T1 trace: benign + A2, training
       seeds 1000-1004 (results/revision5/trace_runs.pkl). The federated models are the means of
       the controllers' local models: D1-D3 from results/e3_ens/models.pkl plus T1. Candidates:
         ens3   v3: mean of RF(D1-D3) and CB(D1-D3)          (6 models)
         ens4   v4: mean of RF(D1-D3, T1) and CB(D1-D3, T1)  (8 models)
         cb4    CatBoost only, mean of CB(D1-D3, T1)          (4 models, about 1/5 of the scoring cost)
       tau per controller at the 0.1 % budget on its own validation benign (T1: seeds 2000-2002).
check  R1-R4 of docs/v4_plan.md for every candidate:
         sim  T1, seeds 3000-3002, A2 / A4 / E9P / benign (5 % of entries per poll)
         tb   the 12 testbed entry-log recordings (seeds 4131-4133, wall clock, s11-s13)
         e11  recall on attacks no controller saw (A6), D1-D3 test_off at the 0.1 % point

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.v4_t1 train
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.v4_t1 check

Writes results/v4/{models.pkl, train_info.json, check_cells.csv, check.md}.
"""
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

from . import ml_compare as M
from .config import DOMAINS, UNSEEN_VARIANTS
from .data import Dataset
from .e1_pair import RF, _rf
from .e1_subsets import _make as _tree
from .models import SkWrap, threshold_at_fpr

OUT = "results/v4"
BUDGET = 0.001
TRAIN_SEEDS = range(1000, 1005)
VAL_SEEDS = (2000, 2001, 2002)
CHECK_SEEDS = (3000, 3001, 3002)
ATTACKS = ("A2", "A4", "E9P")


def _local(make, X, y):
    m = SkWrap(make().fit(X, y))
    if hasattr(m.m, "n_jobs"):
        m.m.n_jobs = 1
    return m


def train():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    runs = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    tr = Dataset.concat([runs[("T1", v, s)] for v in ("A2", None) for s in TRAIN_SEEDS])
    va = Dataset.concat([runs[("T1", None, s)] for s in VAL_SEEDS])
    rf_t1 = _local(lambda: _rf(RF["rf50d12"]), tr.X, tr.y)
    print(f"RF T1 {time.time() - t0:.0f} s", flush=True)
    cb_t1 = _local(lambda: _tree("cb"), tr.X, tr.y)
    print(f"CB T1 {time.time() - t0:.0f} s", flush=True)
    ens3 = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"]
    rf3, cb3 = ens3.ms
    rf4, cb4 = M.Mean(rf3.ms + [rf_t1]), M.Mean(cb3.ms + [cb_t1])
    cands = {"ens3": ens3, "ens4": M.Mean([rf4, cb4]), "cb4": cb4}
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    vben = {d: data[("val", d)].X[data[("val", d)].y == 0] for d in DOMAINS}
    vben["T1"] = va.X[va.y == 0]
    taus = {c: {d: float(threshold_at_fpr(m.predict_proba(X), BUDGET)) for d, X in vben.items()}
            for c, m in cands.items()}
    pickle.dump(dict(cands=cands, rf_t1=rf_t1, cb_t1=cb_t1, taus=taus), open(f"{OUT}/models.pkl", "wb"))
    info = dict(train_rows=int(len(tr.y)), train_attack_rows=int(tr.y.sum()),
                val_benign_rows=int(len(vben["T1"])), budget=BUDGET, taus=taus,
                seconds=round(time.time() - t0))
    json.dump(info, open(f"{OUT}/train_info.json", "w"), indent=1)
    print(json.dumps(info, indent=1))


def _rate(p, y, tau, lab):
    m = y == lab
    return float(100 * (p[m] >= tau).mean()) if m.any() else float("nan")


def check():
    sys.path.insert(0, "testbed")
    import e11_testbed as E
    import entrylog
    t0 = time.time()
    M_ = pickle.load(open(f"{OUT}/models.pkl", "rb"))
    cands, taus = M_["cands"], M_["taus"]
    rows = []
    # sim and tb: per-entry recall (attack rows) and false-positive rate (benign rows) at T1's tau
    src = {}
    for v in ATTACKS + ("benign",):
        src[("sim", v)] = E.concat([E.sim_rows(v, s) for s in CHECK_SEEDS])
        print(f"sim {v} {time.time() - t0:.0f} s", flush=True)
    for v, s, d in E.tb_runs(os.path.expanduser("~/loft-runs/e11tb_T1_*_none_s*")):
        for sw in E.SWITCHES:
            b = entrylog.build(d, sw=sw, frac=0.05, seed=s)
            src.setdefault(("tb", v), []).append({k: b[k] for k in ("X", "y")})
    for v in ATTACKS + ("benign",):
        src[("tb", v)] = E.concat(src[("tb", v)])
    print(f"tb loaded {time.time() - t0:.0f} s", flush=True)
    for (where, v), r in src.items():
        y = r["y"]
        for c, m in cands.items():
            p = m.predict_proba(r["X"])
            tau = taus[c]["T1"]
            rows.append(dict(source=where, variant=v, cand=c, tau=tau, n=len(y),
                             recall=_rate(p, y, tau, 1), fpr=_rate(p, y, tau, 0),
                             attack_median=float(np.median(p[y == 1])) if (y == 1).any() else np.nan))
    # e11: unseen-all recall on D1-D3 test_off at each controller's 0.1 % tau (benign rows from
    # benign runs, as loftbench/e11_detect.py does)
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    for d in DOMAINS:
        D = data[("test_off", d)]
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[x] for x in D.run], dtype=object)
        for c, m in cands.items():
            p = m.predict_proba(D.X)
            for v in UNSEEN_VARIANTS:
                mask = (var == v) | (np.array([x is None for x in var]) & (D.y == 0))
                rows.append(dict(source="e11", variant=f"{v}@{d}", cand=c, tau=taus[c][d],
                                 n=int(mask.sum()), recall=_rate(p[mask], D.y[mask], taus[c][d], 1),
                                 fpr=_rate(p[mask], D.y[mask], taus[c][d], 0), attack_median=np.nan))
        print(f"e11 {d} {time.time() - t0:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/check_cells.csv", index=False)
    report(df)


def report(df):
    g = lambda s, v, c, k: float(df[(df.source == s) & (df.variant == v) & (df.cand == c)][k].iloc[0])  # noqa: E731
    e11 = lambda c: float(df[(df.source == "e11") & (df.cand == c)].recall.mean())  # noqa: E731
    L = ["# EnsGuard v4, phase 2: offline check against the rules fixed in docs/v4_plan.md", "",
         "| Candidate | R1 A4 recall sim / tb (>= 30) | R2 benign FPR sim / tb (<= 0.5) | "
         "R3 A2 recall sim (>= v3 - 2) | R4 E11 unseen recall (>= 46.5) | E9P recall sim / tb | Pass |",
         "|---|---|---|---|---|---|---|"]
    a2_v3 = g("sim", "A2", "ens3", "recall")
    for c in df.cand.unique():
        r1 = (g("sim", "A4", c, "recall"), g("tb", "A4", c, "recall"))
        r2 = (g("sim", "benign", c, "fpr"), g("tb", "benign", c, "fpr"))
        r3 = g("sim", "A2", c, "recall")
        r4 = e11(c)
        ok = min(r1) >= 30 and max(r2) <= 0.5 and r3 >= a2_v3 - 2 and r4 >= 46.5
        L.append(f"| {c} | {r1[0]:.1f} / {r1[1]:.1f} | {r2[0]:.2f} / {r2[1]:.2f} | {r3:.1f} | {r4:.1f} | "
                 f"{g('sim', 'E9P', c, 'recall'):.1f} / {g('tb', 'E9P', c, 'recall'):.1f} | "
                 f"{'yes' if ok else 'no'} |")
    L += ["", "Per-entry rates (%) at the T1 tau; attack_median is the median attack score.", "",
          "```", df[df.source != "e11"].round(3).to_string(index=False), "```"]
    open(f"{OUT}/check.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:3 + len(df.cand.unique()) + 1]))


if __name__ == "__main__":
    {"train": train, "check": check}[sys.argv[1]]()
