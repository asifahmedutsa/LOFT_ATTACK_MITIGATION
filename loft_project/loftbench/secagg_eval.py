"""Secure aggregation and a federated threshold (docs/secagg_plan.md): S1 exactness, S2 fidelity to
lossless federated XGBoost, S3 cost and T1 threshold, on the T1B test rows (seeds 4176-4178).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.secagg_eval     # writes results/secagg/report.md, thresholds.csv

Needs the four runs of fl/secagg_xgb.py (masked, unmasked, and each with --seed 1) and
results/tbfl/fedxgb_hist.json.
"""
import json
import os
import pickle
import sys

import numpy as np

from .data import Dataset
from .models import threshold_at_fpr
from .realfl import ALL, BUDGET
from .tbfl import GROUPS, TEST, VAL
from .tbfl_baselines import metrics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fl"))
import secagg_xgb as sx  # noqa: E402

TB = "results/tbfl"
OUT = "results/secagg"
CAL = {"C1": [("U1t", None, s) for s in (4190, 4191, 4192)], "C2": [("U2t", None, 4190)],
       "C3": [("T1A", None, s) for s in VAL]}
LO, HI, NCELL = -20.0, 20.0, 10000          # public score grid in log-odds (section 3)
NAME = {"A1": "G1", "A2": "G2", "A3": "G3", "A4": "Mimic", "A5": "Spoof", "A6": "Slow", "A7": "Pulse",
        "E9P": "Aware"}


def xgb_scores(X):
    import xgboost as xgb
    b = xgb.Booster(model_file=f"{TB}/fedxgb_hist.json")
    m = b.predict(xgb.DMatrix(X), output_margin=True).astype(np.float64)
    return m


def tau_fed(margins_by_ctrl):
    """Smallest grid edge at which the pooled false-alarm rate is at most the budget; the controllers'
    counts are added by the masked sum."""
    w = (HI - LO) / NCELL
    counts = [np.bincount(np.clip(np.floor((m - LO) / w), 0, NCELL - 1).astype(np.int64), minlength=NCELL)
              .astype(np.float64) for m in margins_by_ctrl]
    tot = np.rint(sx.secure_sum(counts)).astype(np.int64)
    above = np.cumsum(tot[::-1])[::-1]                    # rows in cells >= k
    k = int(np.flatnonzero(above <= BUDGET * tot.sum())[0])
    return LO + k * w


def main():
    runs = pickle.load(open(f"{TB}/rows.pkl", "rb"))
    keys = [(v, s) for v in [None] + ALL for s in TEST]
    test = Dataset.concat([runs[("T1B", v, s)] for v, s in keys])
    owner = np.concatenate([np.full(len(runs[("T1B", v, s)].y), i) for i, (v, s) in enumerate(keys)])
    ben_seed = {s: owner == keys.index((None, s)) for s in TEST}
    ben = np.any(list(ben_seed.values()), 0)
    per = {v: np.isin(owner, [i for i, (w, _) in enumerate(keys) if w == v]) & (test.y == 1) for v in ALL}
    other = np.any([per[v] for v in GROUPS["T1B"]["seen only by another controller"]], 0)
    cal = {c: np.concatenate([runs[k].X[runs[k].y == 0] for k in ks]) for c, ks in CAL.items()}
    uht = runs[("UHt", None, 4190)]
    uht_X = uht.X[uht.y == 0]
    del runs

    M = {n: json.load(open(f"{OUT}/secagg_{n}.json")) for n in ("masked", "unmasked", "masked_s1", "unmasked_s1")}
    margin = {"Lossless federated XGBoost": xgb_scores,
              "Secure-aggregation trainer": lambda X: sx.predict_margin(M["masked"], X)}
    L = ["# Secure aggregation and a federated threshold", "",
         "docs/secagg_plan.md. T1B test rows, seeds 4176-4178 "
         f"({len(test.y):,} rows, {int(ben.sum()):,} benign).", ""]

    # S1: exactness.
    sm = {n: sx.predict_margin(m, test.X) for n, m in M.items()}
    same_trees = all(M[n]["trees"] == M["masked"]["trees"] and M[n]["base_margin"] == M["masked"]["base_margin"]
                     for n in M)
    same_scores = all(np.array_equal(sm[n], sm["masked"]) for n in M)
    L += ["## S1 Exactness", "",
          f"- Trees of the four runs (masked, unmasked, and each rerun with fresh keys) identical in split feature, "
          f"cut, default direction and leaf value: {'yes' if same_trees else 'no'}",
          f"- Scores identical on every test row: {'yes' if same_scores else 'no'}",
          f"- S1: {'pass' if same_trees and same_scores else 'fail'}", ""]

    # Scores, thresholds and measures for both models.
    rows, res = [], {}
    for mname, f in margin.items():
        mt = f(test.X)
        pt = 1 / (1 + np.exp(-mt))
        mc = {c: f(X) for c, X in cal.items()}
        pc = {c: 1 / (1 + np.exp(-m)) for c, m in mc.items()}
        mu = f(uht_X)
        taus = {"tau_C3": float(threshold_at_fpr(pc["C3"], BUDGET)),
                "tau_max": max(float(threshold_at_fpr(pc[c], BUDGET)) for c in CAL),
                "tau_fed": float(1 / (1 + np.exp(-tau_fed(list(mc.values())))))}
        res[mname] = dict(p=pt, taus=taus)
        for tn, tau in taus.items():
            r = dict(model=mname, threshold=tn, tau=tau,
                     false_alarms=100 * float((pt[ben] >= tau).mean()),
                     **{f"false_alarms s{s}": 100 * float((pt[b] >= tau).mean()) for s, b in ben_seed.items()},
                     false_alarms_UHt=100 * float((1 / (1 + np.exp(-mu)) >= tau).mean()),
                     **metrics(pt, test.y, tau),
                     recall_other_controllers=100 * float((pt[other] >= tau).mean()),
                     **{f"recall {NAME[v]}": 100 * float((pt[per[v]] >= tau).mean()) for v in ALL})
            rows.append(r)
    import pandas as pd
    df = pd.DataFrame(rows)
    df.round(4).to_csv(f"{OUT}/thresholds.csv", index=False)

    # S2: fidelity at the same threshold rule (tau_C3).
    a = df[(df.model == "Secure-aggregation trainer") & (df.threshold == "tau_C3")].iloc[0]
    b = df[(df.model == "Lossless federated XGBoost") & (df.threshold == "tau_C3")].iloc[0]
    fa = res["Secure-aggregation trainer"]["p"] >= res["Secure-aggregation trainer"]["taus"]["tau_C3"]
    fb = res["Lossless federated XGBoost"]["p"] >= res["Lossless federated XGBoost"]["taus"]["tau_C3"]
    agree = 100 * float((fa == fb).mean())
    d_f1, d_rc = abs(a.f1 - b.f1), abs(a.recall - b.recall)
    L += ["## S2 Fidelity (threshold rule tau_C3)", "",
          "| Model | Accuracy | Precision | Recall | F1 | False alarms |", "|---|---|---|---|---|---|"]
    for r in (b, a):
        L.append(f"| {r.model} | {r.accuracy:.2f} | {r.precision:.2f} | {r.recall:.2f} | {r.f1:.2f} | "
                 f"{r.false_alarms:.2f} |")
    L += ["", f"- F1 within 1.0 point: {'pass' if d_f1 <= 1 else 'fail'} (difference {d_f1:.2f})",
          f"- Recall within 1.0 point: {'pass' if d_rc <= 1 else 'fail'} (difference {d_rc:.2f})",
          f"- Agreement on at least 99 % of test rows: {'pass' if agree >= 99 else 'fail'} ({agree:.2f} %)", ""]

    # S3: cost.
    lg = {n: json.load(open(f"{OUT}/secagg_{n}_log.json")) for n in M}
    xg = json.load(open(f"{TB}/fedxgb_hist_log.json"))
    L += ["## S3 Cost (reported, not tested)", "",
          "| Run | Training (s) | Masking (s, slowest controller) | Payload (MB) | Loopback (MB) |",
          "|---|---|---|---|---|"]
    for n in M:
        g = lg[n]
        ms = max(p.get("mask_seconds", 0) for p in g["parties"] if p["client"] != "aggregator")
        L.append(f"| {n} | {g['seconds']:.1f} | {ms:.2f} | {g['payload_bytes'] / 1e6:.0f} | "
                 f"{g['loopback_bytes'] / 1e6:.0f} |")
    L.append(f"| fl/run_fedxgb_hist.py (XGBoost, clear) | {xg['seconds']:.1f} | – | – | "
             f"{xg['loopback_bytes'] / 1e6:.0f} |")
    bm, bu = lg["masked"]["payload_bytes"], lg["unmasked"]["payload_bytes"]
    tm, tu = lg["masked"]["seconds"], lg["unmasked"]["seconds"]
    L += ["", f"- Masked payload {100 * (bm / bu - 1):+.1f} % against unmasked (expected within 5 %); "
              f"masked time {100 * (tm / tu - 1):+.1f} % (expected within 25 %).",
          "- The trainer is written in NumPy and XGBoost in C++, so the training times differ by the "
          "implementation, not by the masking. The trainer sends every node's full histogram, where XGBoost "
          "builds one child's histogram and subtracts it from the parent's, so it sends more bytes.", ""]

    # T1: threshold.
    L += ["## T1 Threshold (T1B benign test rows; budget 0.1 %)", "",
          "| Model | Threshold | tau | False alarms % | per seed (4176, 4177, 4178) | UHt false alarms % | "
          "Recall % | F1 % | " + " | ".join(f"Recall {NAME[v]}" for v in ALL) + " |",
          "|" + "---|" * (8 + len(ALL))]
    for _, r in df.iterrows():
        L.append(f"| {r.model} | {r.threshold} | {r.tau:.6f} | {r.false_alarms:.3f} | "
                 + ", ".join(f"{r[f'false_alarms s{s}']:.3f}" for s in TEST)
                 + f" | {r.false_alarms_UHt:.3f} | {r.recall:.2f} | {r.f1:.2f} | "
                 + " | ".join(f"{r[f'recall {NAME[v]}']:.1f}" for v in ALL) + " |")
    x = df[df.model == "Lossless federated XGBoost"].set_index("threshold")
    L += ["", f"- On the XGBoost model, false alarms under tau_fed {x.loc['tau_fed', 'false_alarms']:.3f} % against "
              f"{x.loc['tau_C3', 'false_alarms']:.3f} % under tau_C3: "
              f"{'lower' if x.loc['tau_fed', 'false_alarms'] < x.loc['tau_C3', 'false_alarms'] else 'not lower'}; "
              f"recall {x.loc['tau_fed', 'recall']:.2f} % against {x.loc['tau_C3', 'recall']:.2f} %. "
              "One comparison, not a significance test."]
    open(f"{OUT}/report.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
