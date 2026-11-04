"""Does the agreement rule add anything over a stricter threshold on one model?

Members: the federated RF (50 trees, depth 12) and CatBoost of e1_pair, each with tau at the
1 % benign budget on validation. Agreement policy: hard action when both members flag an entry,
soft action when only one does. Each competitor is a single score with two thresholds: hard
above tau_h, soft between tau and tau_h, where tau_h is set on validation so that its benign
hard-action rate equals the agreement policy's benign hard-action rate on validation. All
thresholds come from validation data; the test split is used only for the report.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e1_agree

Writes results/e1_agree/rates.csv: per policy and exposure, the benign and attack shares that
get a hard action and that get any action.
"""
import os
import pickle

import numpy as np
import pandas as pd

from . import ml_compare as M
from .config import DOMAINS
from .e1_pair import RF, _fit, _rf
from .e1_subsets import _make
from .models import threshold_at_fpr

OUT = "results/e1_agree"


def main():
    os.makedirs(OUT, exist_ok=True)
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tr = {d: data[("train", d)] for d in DOMAINS}
    rf, _ = _fit(lambda: _rf(RF["rf50d12"]), tr)
    cb, _ = _fit(lambda: _make("cb"), tr)
    print("  trained", flush=True)
    rows = []
    for d in DOMAINS:
        v, D = data[("val", d)], data[("test_off", d)]
        vb = v.y == 0
        pv = {"rf": rf.predict_proba(v.X), "cb": cb.predict_proba(v.X)}
        pv["vote"] = (pv["rf"] + pv["cb"]) / 2
        pt = {"rf": rf.predict_proba(D.X), "cb": cb.predict_proba(D.X)}
        pt["vote"] = (pt["rf"] + pt["cb"]) / 2
        tau = {k: threshold_at_fpr(pv[k][vb], M.BUDGET) for k in pv}
        hard_v = (pv["rf"] >= tau["rf"]) & (pv["cb"] >= tau["cb"])
        target = float(hard_v[vb].mean())
        pol = {"agreement": ((pt["rf"] >= tau["rf"]) & (pt["cb"] >= tau["cb"]),
                             (pt["rf"] >= tau["rf"]) | (pt["cb"] >= tau["cb"]))}
        for k in pv:
            tau_h = threshold_at_fpr(pv[k][vb], target)
            pol[f"{k} strict"] = (pt[k] >= tau_h, pt[k] >= tau[k])
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        groups = {"benign": D.y == 0}
        for exp in ("seen-local", "seen-remote", "unseen-all"):
            vs = [x for x in set(var) if x is not None and M._exposure(d, x) == exp]
            groups[f"attack {exp}"] = (D.y == 1) & np.isin(var, vs)
        for name, (hard, anyact) in pol.items():
            for g, msk in groups.items():
                if msk.sum() == 0:
                    continue
                rows.append(dict(domain=d, policy=name, group=g, val_target=target,
                                 hard=float(hard[msk].mean()), any=float(anyact[msk].mean())))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "rates.csv"), index=False)
    tab = (df.groupby(["policy", "group"])[["hard", "any"]].mean() * 100).round(2)
    pd.set_option("display.width", 200)
    print(tab.unstack("group").to_string())
    print("validation benign hard-action target (%):",
          (df.groupby("domain")["val_target"].first() * 100).round(3).to_dict())


if __name__ == "__main__":
    main()
