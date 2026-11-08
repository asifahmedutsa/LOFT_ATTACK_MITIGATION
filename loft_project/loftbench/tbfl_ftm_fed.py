"""Exploratory (8 November 2026): FTMaster's rule classifier trained by lossless federated XGBoost (fl/run_fedxgb_hist.py with
FL_DATA=results/tbfl/fl_data_ftm, FL_TREES=200, FL_PARAMS={\"eta\": 0.3}, FL_NAME=fedxgb_ftmaster) against pooled FTMaster on
the T1B test rows. Writes results/tbfl/ftmaster_federated.csv.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_ftm_fed
"""
import json, pickle
import numpy as np, pandas as pd
from loftbench.baselines import ftmaster_rule_features
from loftbench.data import Dataset
from loftbench.models import threshold_at_fpr
from loftbench.realfl import ALL, BUDGET, Booster
from loftbench.tbfl import CTRL, OUT, TEST, VAL, train_rows
from loftbench.tbfl_baselines import metrics, fit, p1
runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
cal = Dataset.concat([runs[("T1A", None, s)] for s in VAL]); cal = cal.X[cal.y == 0]
keys = [(v, s) for v in [None] + ALL for s in TEST]
alla = Dataset.concat([runs[("T1B", v, s)] for v, s in keys])
owner = np.concatenate([np.full(len(runs[("T1B", v, s)].y), i) for i, (v, s) in enumerate(keys)])
ben = np.isin(owner, [i for i, (v, _) in enumerate(keys) if v is None])
per = {v: np.isin(owner, [i for i, (w, _) in enumerate(keys) if w == v]) & (alla.y == 1) for v in ALL}
pooled = Dataset.concat([train_rows(runs, c) for c in CTRL]); del runs
Fa, Fc = ftmaster_rule_features(alla.X), ftmaster_rule_features(cal)
fed = Booster(f"{OUT}/fedxgb_ftmaster.json")
pool = fit("FTMaster", pooled); del pooled
rows = []
for name, m in (("FTMaster, lossless federated", fed), ("FTMaster, pooled (no privacy)", pool)):
    pa, pc = p1(m, Fa), p1(m, Fc)
    for rule in ("0.5 (paper)", "0.1 % of T1A benign"):
        tau = 0.5 if rule.startswith("0.5") else float(threshold_at_fpr(pc, BUDGET))
        r = dict(method=name, training="testbed, C1-C3", threshold=rule, tau=tau,
                 false_alarms=100 * float((pa[ben] >= tau).mean()))
        r.update(metrics(pa, alla.y, tau))
        for v in ALL:
            r[f"recall {v}"] = 100 * float((pa[per[v]] >= tau).mean())
        rows.append(r)
    if name.startswith("FTMaster, l"):
        pf = pa
    else:
        print("max |federated - pooled| probability on test rows:", float(np.abs(pf - pa).max()))
t = pd.DataFrame(rows)
t.round(4).to_csv(f"{OUT}/ftmaster_federated.csv", index=False)
print(t[["method", "threshold", "false_alarms", "recall", "f1", "mcc", "recall A4", "recall A6", "recall E9P"]].round(2).to_string(index=False))
