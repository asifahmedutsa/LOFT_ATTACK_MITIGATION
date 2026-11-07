"""E11 for FEVER's detector: the three shared CatBoost models (results/v21/exported/ens_config_v5.json,
the deployed files), scored exactly as loftbench.e11_detect scores every other detector (same
test_off rows, tau at a 0.1 % benign rate on each controller's validation data, same metrics and
exposure groups).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e11_fever

Writes results/e11_detect/{cells_fever.csv, table_fever.csv}.
"""
import json
import os
import pickle

import numpy as np
import pandas as pd

from .config import DOMAINS, VARIANTS
from .e11_detect import OPS, OUT, _exposure, _metrics
from .ensjson import EnsembleJSON
from .models import threshold_at_fpr


def main():
    ec = json.load(open("results/v21/exported/ens_config_v5.json"))
    model = EnsembleJSON("results/v21/exported", ec)
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    rows = []
    for d in DOMAINS:
        D, V = data[("test_off", d)], data[("val", d)]
        p = model.predict_proba(D.X)
        vb = model.predict_proba(V.X[V.y == 0])
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben_run = np.array([x is None for x in var])
        for op in ("fpr0.1",):
            tau = threshold_at_fpr(vb, OPS[op])
            for v in VARIANTS:
                mask = (var == v) | (ben_run & (D.y == 0))
                rows.append(dict(detector="fever", training="federated", op=op, domain=d, variant=v,
                                 exposure=_exposure(d, v), tau=tau, **_metrics(D.y[mask], p[mask], tau)))
        print(" ", d, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "cells_fever.csv"), index=False)
    cols = ["accuracy", "precision", "recall", "f1", "fpr", "auc", "pr_auc"]
    tab = (df.groupby(["detector", "op", "exposure"])[cols].mean() * 100).round(2).reset_index()
    tab.to_csv(os.path.join(OUT, "table_fever.csv"), index=False)
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
