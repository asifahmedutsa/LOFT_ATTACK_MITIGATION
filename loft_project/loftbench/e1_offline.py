"""E1: the offline classification table the related papers print (Acc, P, R, F1, FPR, FNR, MCC).

Families: the deployed MLP (v2.1), Random Forest, histogram gradient boosting and CatBoost (the
model of DMS-BTT and FloRa), each trained local / federated / pooled on the saved v2 datasets as
in ml_compare (trees federate by averaging the controllers' models' probabilities). Thresholds
at the 1 % benign budget on local validation data. Test: the offline test split, per controller
and attack, grouped by exposure (seen locally, seen only by another controller, seen by none).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e1_offline

Writes results/e1_offline/{offline.csv, table.csv, train_info.json}.
"""
import json
import os
import pickle
import time

import numpy as np
import pandas as pd

from . import ml_compare as M
from .config import DOMAINS
from .models import SkWrap, threshold_at_fpr

OUT = "results/e1_offline"


def _cat():
    from catboost import CatBoostClassifier
    return CatBoostClassifier(iterations=300, depth=6, verbose=0, random_seed=0, thread_count=4)


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    models, taus, info = M.train(data)
    tr = {d: data[("train", d)] for d in DOMAINS}
    t1 = time.time()
    local = {d: SkWrap(_cat().fit(tr[d].X, tr[d].y)) for d in DOMAINS}
    pooled = SkWrap(_cat().fit(np.concatenate([tr[d].X for d in DOMAINS]),
                               np.concatenate([tr[d].y for d in DOMAINS])))
    fed = M.Mean(list(local.values()))
    for d in DOMAINS:
        for how, m in (("local", local[d]), ("federated", fed), ("pooled", pooled)):
            models[("catboost", how, d)] = m
            v = data[("val", d)]
            taus[("catboost", how, d)] = threshold_at_fpr(m.predict_proba(v.X[v.y == 0]), M.BUDGET)
    info["catboost"] = dict(train_seconds=round(time.time() - t1, 1),
                            model_bytes=len(pickle.dumps(local["D1"].m)))
    rows = pd.DataFrame(M.offline(data, models, taus))
    rows.to_csv(os.path.join(OUT, "offline.csv"), index=False)
    cols = ["accuracy", "precision", "recall", "f1", "fpr", "fnr", "mcc", "auc"]
    tab = (rows.groupby(["model", "training", "exposure"])[cols].mean() * 100).round(2)
    tab.to_csv(os.path.join(OUT, "table.csv"))
    pd.set_option("display.width", 200)
    print(tab.to_string())
    info["total_seconds"] = round(time.time() - t0)
    json.dump(info, open(os.path.join(OUT, "train_info.json"), "w"), indent=2)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
