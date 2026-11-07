"""FEVER's detector trained on real traffic (docs/realfl_plan.md).

Controllers C1 (univ2 part 0, A1 + A4), C2 (univ2 part 3, A2 + A5) and C3 (bigFlows T1A, A3 + A7);
test networks T1B (C3's own network, later part of the capture) and UH (univ2 part 6, no
controller). Every network replays real traffic in the simulator; attacks are generated.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.realfl collect    # labelled rows
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.realfl central    # local, one-shot, pooled
    ~/.venvs/fl/bin/python fl/run_fedxgb.py                              # Flower federated XGBoost
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.realfl evaluate   # exposure table and choice

Writes results/realfl/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .data import Dataset, collect_run  # noqa: E402
from .experiment import COLLECT_CFG, SPLITS  # noqa: E402
from .models import SkWrap, threshold_at_fpr  # noqa: E402

OUT = "results/realfl"
CTRL = {"C1": ("U1", ["A1", "A4"]), "C2": ("U2", ["A2", "A5"]), "C3": ("T1A", ["A3", "A7"])}
ALL = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "E9P"]
VAL = (2000, 2001, 2002)
TEST = (3000, 3001, 3002)
BUDGET = 0.001
# Exposure groups seen from the network where the detector is used.
GROUPS = {"T1B": {"seen locally": ["A3", "A7"], "seen only by another controller": ["A1", "A2", "A4", "A5"],
                  "seen by no one": ["A6", "E9P"]},
          "UH": {"seen by some controller": ["A1", "A2", "A3", "A4", "A5", "A7"],
                 "seen by no one": ["A6", "E9P"]}}
CALIB = {"T1B": "T1A", "UH": "UH"}          # benign rows that set each test network's threshold
TESTDOM = {"T1B": "T1Bt", "UH": "UH"}       # T1B replayed at the testbed's 600 pps


def _run(args):
    d, v, s = args
    return d, v, s, collect_run(d, v, s, COLLECT_CFG)


def stage_collect():
    os.makedirs(OUT, exist_ok=True)
    tasks = [(d, v, s) for d, att in CTRL.values() for v in att + [None] for s in SPLITS["train"]]
    tasks += [(d, None, s) for d in CALIB.values() for s in VAL]
    tasks += [(TESTDOM[d], v, s) for d in GROUPS for v in ALL + [None] for s in TEST]
    t0 = time.time()
    runs = {}
    with get_context("fork").Pool(4) as p:
        for i, (d, v, s, ds) in enumerate(p.imap_unordered(_run, tasks, chunksize=1)):
            runs[(d, v, s)] = ds
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(tasks)} runs, {time.time() - t0:.0f} s", flush=True)
    pickle.dump(runs, open(f"{OUT}/runs.pkl", "wb"))
    info = {f"{d}/{v}/{s}": dict(rows=int(len(r.y)), attack=int(r.y.sum())) for (d, v, s), r in runs.items()}
    info["seconds"] = round(time.time() - t0)
    json.dump(info, open(f"{OUT}/collect_info.json", "w"), indent=1)
    # One file per controller for the Flower clients (features and labels only).
    os.makedirs(f"{OUT}/fl_data", exist_ok=True)
    for c, (d, att) in CTRL.items():
        ds = Dataset.concat([runs[(d, v, s)] for v in att + [None] for s in SPLITS["train"]])
        np.savez_compressed(f"{OUT}/fl_data/{c}.npz", X=ds.X.astype(np.float32), y=ds.y.astype(np.int8))
        print(c, d, len(ds.y), "rows,", int(ds.y.sum()), "attack")
    print(f"collected {len(tasks)} runs in {time.time() - t0:.0f} s")


def _runs():
    return pickle.load(open(f"{OUT}/runs.pkl", "rb"))


def train_rows(runs, c):
    d, att = CTRL[c]
    return Dataset.concat([runs[(d, v, s)] for v in att + [None] for s in SPLITS["train"]])


def _cb(X, y, seed=0):
    from catboost import CatBoostClassifier
    return SkWrap(CatBoostClassifier(iterations=300, depth=6, verbose=0, random_seed=seed,
                                     thread_count=4).fit(X, y))


def _xgb(X, y, seed=0):
    import xgboost as xgb
    return SkWrap(xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, tree_method="hist",
                                    n_jobs=4, random_state=seed).fit(X, y))


class Mean:
    """One-shot sharing: average of the controllers' local models' probabilities."""

    def __init__(self, ms):
        self.ms = ms

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.ms], axis=0)


def stage_central():
    runs = _runs()
    t0 = time.time()
    tr = {c: train_rows(runs, c) for c in CTRL}
    pooled = Dataset.concat(list(tr.values()))
    models = {}
    for c in CTRL:
        models[f"local CatBoost {c}"] = _cb(tr[c].X, tr[c].y)
        models[f"local XGBoost {c}"] = _xgb(tr[c].X, tr[c].y)
        print(c, f"{time.time() - t0:.0f} s", flush=True)
    models["one-shot CatBoost"] = Mean([models[f"local CatBoost {c}"] for c in CTRL])
    models["one-shot XGBoost"] = Mean([models[f"local XGBoost {c}"] for c in CTRL])
    models["pooled CatBoost"] = _cb(pooled.X, pooled.y)
    models["pooled XGBoost"] = _xgb(pooled.X, pooled.y)
    pickle.dump(models, open(f"{OUT}/central_models.pkl", "wb"))
    print(f"central models in {time.time() - t0:.0f} s")


class Booster:
    """A Flower-trained XGBoost model saved as JSON."""

    def __init__(self, path):
        import xgboost as xgb
        self.b = xgb.Booster()
        self.b.load_model(path)

    def predict_proba(self, X):
        import xgboost as xgb
        return self.b.predict(xgb.DMatrix(np.asarray(X, np.float32)))


def _metrics(p, y, tau):
    flag = p >= tau
    tp, fp = int((flag & (y == 1)).sum()), int((flag & (y == 0)).sum())
    fn, tn = int((~flag & (y == 1)).sum()), int((~flag & (y == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return dict(accuracy=100 * (tp + tn) / max(len(y), 1), precision=100 * prec, recall=100 * rec,
                f1=100 * 2 * prec * rec / max(prec + rec, 1e-12), fpr=100 * fp / max(fp + tn, 1))


def stage_evaluate():
    runs = _runs()
    models = pickle.load(open(f"{OUT}/central_models.pkl", "rb"))
    named = {"Local only (C3)": models["local CatBoost C3"],
             "One-shot sharing (CatBoost)": models["one-shot CatBoost"],
             "One-shot sharing (XGBoost)": models["one-shot XGBoost"],
             "Pooled (CatBoost)": models["pooled CatBoost"],
             "Pooled (XGBoost)": models["pooled XGBoost"]}
    if os.path.exists(f"{OUT}/fedxgb.json"):
        named["Federated XGBoost (Flower)"] = Booster(f"{OUT}/fedxgb.json")
    if os.path.exists(f"{OUT}/fedxgb_cyclic.json"):           # exploratory: not in the choice rule
        named["Cyclic federated XGBoost (exploratory)"] = Booster(f"{OUT}/fedxgb_cyclic.json")
    if os.path.exists(f"{OUT}/fedprox.npz"):
        from .models import MLP, Standardizer
        z = np.load(f"{OUT}/fedprox.npz")
        w = [z[f"arr_{i}"] for i in range(4)]
        m = MLP(w[0].shape[0], w[0].shape[1])
        m.set_weights(w)
        m.scaler = Standardizer(z["mean"], z["std"])
        named["FedProx (Flower)"] = m
    rows = []
    for net, groups in GROUPS.items():
        cal = Dataset.concat([runs[(CALIB[net], None, s)] for s in VAL])
        for name, m in named.items():
            tau = threshold_at_fpr(m.predict_proba(cal.X[cal.y == 0]), BUDGET)
            ben = Dataset.concat([runs[(TESTDOM[net], None, s)] for s in TEST])
            r = dict(network=net, detector=name, tau=tau,
                     benign_fpr=_metrics(m.predict_proba(ben.X), ben.y, tau)["fpr"])
            for g, vs in groups.items():
                ds = Dataset.concat([runs[(TESTDOM[net], v, s)] for v in vs for s in TEST])
                for k, val in _metrics(m.predict_proba(ds.X), ds.y, tau).items():
                    r[f"{g}: {k}"] = val
            for v in ALL:
                ds = Dataset.concat([runs[(TESTDOM[net], v, s)] for s in TEST])
                r[f"recall {v}"] = _metrics(m.predict_proba(ds.X), ds.y, tau)["recall"]
            rows.append(r)
            print(net, name, {k: round(v, 2) for k, v in r.items() if "recall" in k and ":" in k}, flush=True)
    t = pd.DataFrame(rows)
    t.round(3).to_csv(f"{OUT}/exposure.csv", index=False)
    # The choice rule (docs/realfl_plan.md), on T1B.
    T = t[t.network == "T1B"].set_index("detector")

    def score(d):
        return (T.loc[d, "seen only by another controller: recall"] + T.loc[d, "seen by no one: recall"]) / 2
    one = score("One-shot sharing (CatBoost)")
    choice, why = "One-shot sharing (CatBoost)", "rule 3"
    if "Federated XGBoost (Flower)" in T.index:
        f = "Federated XGBoost (Flower)"
        if score(f) >= one - 1 and T.loc[f, "benign_fpr"] <= 0.2:
            choice, why = f, "rule 1"
    if choice.startswith("One-shot") and "FedProx (Flower)" in T.index:
        f = "FedProx (Flower)"
        fx = score("Federated XGBoost (Flower)") if "Federated XGBoost (Flower)" in T.index else -1
        if score(f) >= max(one, fx) + 2 and T.loc[f, "benign_fpr"] <= 0.2:
            choice, why = f, "rule 2"
    scores = {d: round(score(d), 2) for d in T.index}
    json.dump(dict(choice=choice, rule=why, scores_T1B=scores), open(f"{OUT}/choice.json", "w"), indent=1)
    print("scores on T1B:", scores)
    print("FEVER's detector:", choice, f"({why})")


if __name__ == "__main__":
    {"collect": stage_collect, "central": stage_central, "evaluate": stage_evaluate}[sys.argv[1]]()
