"""Controller configs for the deployment check (docs/testbed_training_plan.md, amendment 1):
the Flower bagging and lossless federated XGBoost models trained on testbed rows, as TreeJSON.

    PYTHONPATH=. ~/.venvs/fl/bin/python -m loftbench.tbfl_export

Writes results/v21/exported/tb_xgb_{bag,ll}.json and ens_config_fl_{bag,ll}.json (v6's block
rule, rho and volume rule; the detector and its T1B threshold replaced). Thresholds as in
loftbench.tbfl: 0.1 % of the T1A benign rows of seeds 4173-4175. Parity is checked on T1B test rows.
"""
import json
import pickle

import numpy as np
import xgboost as xgb

from .data import Dataset
from .models import threshold_at_fpr
from .tbfl import OUT, TEST, VAL
from .treejson import TreeJSON

EXP = "results/v21/exported"
BUDGET = 0.001
MODELS = {"bag": ("fedxgb.json", "Federated XGBoost bagging (Flower), testbed rows"),
          "ll": ("fedxgb_hist.json", "Lossless federated XGBoost, testbed rows")}


def tree_dict(b, X):
    js = json.loads(b.save_raw("json").decode())
    trees = []
    for t in js["learner"]["gradient_booster"]["model"]["trees"]:
        lc = np.asarray(t["left_children"], int)
        cond = np.asarray(t["split_conditions"], float)
        trees.append(dict(feature=t["split_indices"], threshold=cond.tolist(), left=lc.tolist(),
                          right=t["right_children"], value=np.where(lc < 0, cond, 0.0).tolist()))
    d = dict(kind="xgb", base_margin=0.0, trees=trees)
    p = TreeJSON(d).predict_proba(X[:200])[:, 1]
    d["base_margin"] = float(np.median(b.predict(xgb.DMatrix(X[:200]), output_margin=True) - np.log(p / (1 - p))))
    return d


def main():
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    cal = Dataset.concat([runs[("T1A", None, s)] for s in VAL])
    cal = cal.X[cal.y == 0].astype(np.float32)
    test = Dataset.concat([r for (d, v, s), r in runs.items() if d == "T1B" and s in TEST]).X.astype(np.float32)
    rng = np.random.default_rng(0)
    chk = test[rng.choice(len(test), 20000, replace=False)]
    base = json.load(open(f"{EXP}/ens_config_v6.json"))
    out = {}
    for k, (f, what) in MODELS.items():
        b = xgb.Booster()
        b.load_model(f"{OUT}/{f}")
        d = tree_dict(b, chk)
        json.dump(d, open(f"{EXP}/tb_xgb_{k}.json", "w"))
        tj = TreeJSON(f"{EXP}/tb_xgb_{k}.json")
        err = float(np.abs(tj.predict_proba(chk)[:, 1] - b.predict(xgb.DMatrix(chk))).max())
        assert err < 1e-4, (k, err)
        tau = float(threshold_at_fpr(b.predict(xgb.DMatrix(cal)), BUDGET))
        cfg = dict(base, selected=f"{what} (docs/testbed_training_plan.md, amendment 1)",
                   cb=[], rf=[], xgb=[f"tb_xgb_{k}.json"], tau={"T1B": tau})
        cfg.pop("fast_cb", None)
        json.dump(cfg, open(f"{EXP}/ens_config_fl_{k}.json", "w"), indent=1)
        out[k] = dict(model=f, tau_T1B=tau, parity_max_abs_diff=err, trees=len(d["trees"]))
        print(k, out[k])
    json.dump(out, open(f"{OUT}/export.json", "w"), indent=1)


if __name__ == "__main__":
    main()
