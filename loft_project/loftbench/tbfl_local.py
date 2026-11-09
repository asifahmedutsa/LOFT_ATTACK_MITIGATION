"""FEVER without sharing (docs/final_campaign_prereg.md, section 3, fever-ll-local): XGBoost with the
lossless federated model's settings (fl/run_fedxgb_hist.py: 300 trees, eta 0.1, depth 6, hist, 256
bins, seed 0) trained on C3's rows only, its threshold by the same rule (0.1 % of the T1A benign rows
of seeds 4173-4175), exported as loftbench.tbfl_export exports the deployed one.

    PYTHONPATH=. ~/.venvs/fl/bin/python -m loftbench.tbfl_local

Writes results/tbfl/xgb_local_C3.json (the booster), results/v21/exported/tb_xgb_local.json and
ens_config_ll_local.json (ens_config_fl_ll.json with the detector and its T1B threshold replaced).
nthread 4 instead of 1: a speed setting only.
"""
import json
import pickle
import time

import numpy as np
import xgboost as xgb

from .data import Dataset
from .models import threshold_at_fpr
from .tbfl import OUT, TEST, VAL
from .tbfl_export import BUDGET, EXP, tree_dict
from .treejson import TreeJSON

PARAMS = dict(objective="binary:logistic", eta=0.1, max_depth=6, tree_method="hist", max_bin=256,
              nthread=4, eval_metric="logloss", seed=0)
TREES = 300


def main():
    t0 = time.time()
    d = np.load(f"{OUT}/fl_data/C3.npz")
    b = xgb.train(PARAMS, xgb.DMatrix(d["X"], label=d["y"]), TREES)
    b.save_model(f"{OUT}/xgb_local_C3.json")
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    cal = Dataset.concat([runs[("T1A", None, s)] for s in VAL])
    cal = cal.X[cal.y == 0].astype(np.float32)
    test = Dataset.concat([r for (dm, v, s), r in runs.items() if dm == "T1B" and s in TEST])
    del runs
    rng = np.random.default_rng(0)
    chk = test.X[rng.choice(len(test.y), 20000, replace=False)].astype(np.float32)
    td = tree_dict(b, chk)
    json.dump(td, open(f"{EXP}/tb_xgb_local.json", "w"))
    err = float(np.abs(TreeJSON(f"{EXP}/tb_xgb_local.json").predict_proba(chk)[:, 1] - b.predict(xgb.DMatrix(chk))).max())
    assert err < 1e-4, err
    tau = float(threshold_at_fpr(b.predict(xgb.DMatrix(cal)), BUDGET))
    base = json.load(open(f"{EXP}/ens_config_fl_ll.json"))
    cfg = dict(base, selected="XGBoost on C3's rows only, the lossless model's settings (FEVER without sharing)",
               xgb=["tb_xgb_local.json"], tau={"T1B": tau})
    json.dump(cfg, open(f"{EXP}/ens_config_ll_local.json", "w"), indent=1)
    info = dict(rows=int(len(d["y"])), attack=int(d["y"].sum()), trees=len(td["trees"]), tau_T1B=tau,
                parity_max_abs_diff=err, seconds=round(time.time() - t0))
    json.dump(info, open(f"{OUT}/xgb_local_C3_info.json", "w"), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
