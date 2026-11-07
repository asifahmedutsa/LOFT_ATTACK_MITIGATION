"""FEVER's detector trained on rows recorded on the testbed (docs/testbed_training_plan.md).

Recordings: testbed/record_tbtrain.sh (~/loft-runs/tbt_<domain>_<variant>_none_s<seed>, entry log
on). Rows: testbed/entrylog.py on the controller's poll times, all three switches, 5 % of entries
per poll, labelled from ground truth.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl rows       # rows.pkl and fl_data/C*.npz
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl central    # local, one-shot, pooled
    FL_OUT=results/tbfl ~/.venvs/fl/bin/python fl/run_fedxgb.py        # Flower bagging
    FL_OUT=results/tbfl ~/.venvs/fl/bin/python fl/run_fedprox.py       # Flower FedProx
    FL_OUT=results/tbfl ~/.venvs/fl/bin/python fl/run_fedxgb_hist.py   # lossless federated XGBoost
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl evaluate   # metrics, exposure, choice

Writes results/tbfl/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import glob  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .data import Dataset  # noqa: E402
from .models import threshold_at_fpr  # noqa: E402
from .realfl import ALL, BUDGET, Booster, Mean, _cb, _metrics, _xgb  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testbed"))
import entrylog  # noqa: E402

OUT = os.environ.get("TBFL_OUT", "results/tbfl")
RUNS = os.environ.get("TBFL_RUNS", os.path.expanduser("~/loft-runs"))
TAG = os.environ.get("TBFL_TAG", "tbt")
SWITCHES = ("s11", "s12", "s13")
FRAC = 0.05
CTRL = {"C1": ("U1t", ["A1", "A4"]), "C2": ("U2t", ["A2", "A5"]), "C3": ("T1A", ["A3", "A7"])}
TRAIN, VAL, TEST = (4170, 4171, 4172), (4173, 4174, 4175), (4176, 4177, 4178)
TESTNET = {"T1B": ("T1B", "T1A"), "UH": ("UHt", None)}     # network: (domain, threshold domain)
GROUPS = {"T1B": {"seen locally": ["A3", "A7"], "seen only by another controller": ["A1", "A2", "A4", "A5"],
                  "seen by no one": ["A6", "E9P"]},
          "UH": {"seen by some controller": ["A1", "A2", "A3", "A4", "A5", "A7"],
                 "seen by no one": ["A6", "E9P"]}}
FEDERATED = ["One-shot sharing (CatBoost)", "Federated XGBoost bagging (Flower)", "FedProx (Flower)",
             "Lossless federated XGBoost"]          # least shared first (the choice rule's order)


def _build(args):
    d, dom, v, s = args
    parts = []
    for sw in SWITCHES:
        b = entrylog.build(d, sw=sw, domain=dom, clock="wall", frac=FRAC, seed=s)
        parts.append(b)
    X = np.concatenate([b["X"] for b in parts])
    n = len(X)
    ds = Dataset(X, np.concatenate([b["dms"] for b in parts]), np.concatenate([b["y"] for b in parts]).astype(np.int8),
                 np.full(n, s), np.concatenate([b["t"] for b in parts]), np.zeros((0, 5)),
                 [dict(domain=dom, variant=v, seed=s, run_dir=d)])
    return (dom, None if v == "benign" else v, s), ds


def stage_rows():
    os.makedirs(OUT, exist_ok=True)
    pat = re.compile(rf"{TAG}_(\w+?)_(A\d|E9P|benign)_none_s(\d+)$")
    tasks = []
    for d in sorted(glob.glob(os.path.join(RUNS, f"{TAG}_*_none_s*"))):
        m = pat.search(os.path.basename(d))
        if m and os.path.exists(os.path.join(d, "summary.txt")):
            tasks.append((d, m.group(1), m.group(2), int(m.group(3))))
    t0 = time.time()
    with get_context("fork").Pool(4) as p:
        runs = dict(p.map(_build, tasks, chunksize=1))
    pickle.dump(runs, open(f"{OUT}/rows.pkl", "wb"))
    info = {f"{d}/{v}/{s}": dict(rows=int(len(r.y)), attack=int(r.y.sum())) for (d, v, s), r in sorted(
        runs.items(), key=lambda kv: str(kv[0]))}
    json.dump(info, open(f"{OUT}/rows_info.json", "w"), indent=1)
    os.makedirs(f"{OUT}/fl_data", exist_ok=True)
    for c, (dom, att) in CTRL.items():
        ds = train_rows(runs, c)
        np.savez_compressed(f"{OUT}/fl_data/{c}.npz", X=ds.X.astype(np.float32), y=ds.y.astype(np.int8))
        print(c, dom, len(ds.y), "rows,", int(ds.y.sum()), "attack")
    print(f"{len(tasks)} recordings in {time.time() - t0:.0f} s")


def _runs():
    return pickle.load(open(f"{OUT}/rows.pkl", "rb"))


def train_rows(runs, c):
    dom, att = CTRL[c]
    return Dataset.concat([runs[(dom, v, s)] for v in att + [None] for s in TRAIN])


def stage_central():
    runs = _runs()
    tr = {c: train_rows(runs, c) for c in CTRL}
    pooled = Dataset.concat(list(tr.values()))
    models = {}
    for c in CTRL:
        models[f"local CatBoost {c}"] = _cb(tr[c].X, tr[c].y)
    models["one-shot CatBoost"] = Mean([models[f"local CatBoost {c}"] for c in CTRL])
    models["pooled CatBoost"] = _cb(pooled.X, pooled.y)
    models["pooled XGBoost"] = _xgb(pooled.X, pooled.y)
    pickle.dump(models, open(f"{OUT}/central_models.pkl", "wb"))


def detectors():
    from .models import MLP, Standardizer
    models = pickle.load(open(f"{OUT}/central_models.pkl", "rb"))
    named = {"Local only (C3)": models["local CatBoost C3"],
             "One-shot sharing (CatBoost)": models["one-shot CatBoost"],
             "Pooled (CatBoost)": models["pooled CatBoost"], "Pooled (XGBoost)": models["pooled XGBoost"],
             "Federated XGBoost bagging (Flower)": Booster(f"{OUT}/fedxgb.json"),
             "Lossless federated XGBoost": Booster(f"{OUT}/fedxgb_hist.json")}
    z = np.load(f"{OUT}/fedprox.npz")
    w = [z[f"arr_{i}"] for i in range(4)]
    m = MLP(w[0].shape[0], w[0].shape[1])
    m.set_weights(w)
    m.scaler = Standardizer(z["mean"], z["std"])
    named["FedProx (Flower)"] = m
    return named


def stage_evaluate():
    runs = _runs()
    named = detectors()
    rows = []
    for net, (dom, cal_dom) in TESTNET.items():
        if not all((dom, v, s) in runs for v in ALL + [None] for s in TEST):
            print(f"{net}: test recordings incomplete, skipped")
            continue
        cal = Dataset.concat([runs[(cal_dom, None, s)] for s in VAL]) if cal_dom else None
        ben = Dataset.concat([runs[(dom, None, s)] for s in TEST])
        alla = Dataset.concat([runs[(dom, v, s)] for v in ALL + [None] for s in TEST])
        for name, m in named.items():
            if cal is not None:
                tau = threshold_at_fpr(m.predict_proba(cal.X[cal.y == 0]), BUDGET)
            else:                           # UH has no controller: its own test benign (an oracle)
                tau = threshold_at_fpr(m.predict_proba(ben.X), BUDGET)
            r = dict(network=net, detector=name, tau=tau, benign_fpr=_metrics(m.predict_proba(ben.X), ben.y, tau)["fpr"])
            for k, val in _metrics(m.predict_proba(alla.X), alla.y, tau).items():
                r[f"all: {k}"] = val
            for g, vs in GROUPS[net].items():
                ds = Dataset.concat([runs[(dom, v, s)] for v in vs for s in TEST])
                for k, val in _metrics(m.predict_proba(ds.X), ds.y, tau).items():
                    r[f"{g}: {k}"] = val
            for v in ALL:
                ds = Dataset.concat([runs[(dom, v, s)] for s in TEST])
                met = _metrics(m.predict_proba(ds.X), ds.y, tau)
                r[f"recall {v}"] = met["recall"]
            rows.append(r)
            print(net, name, {k: round(v, 2) for k, v in r.items() if k.endswith("recall")}, flush=True)
    t = pd.DataFrame(rows)
    t.round(3).to_csv(f"{OUT}/exposure.csv", index=False)
    T = t[t.network == "T1B"].set_index("detector")

    def score(d):
        return float((T.loc[d, "seen only by another controller: recall"] + T.loc[d, "seen by no one: recall"]) / 2)
    ok = [d for d in FEDERATED if T.loc[d, "benign_fpr"] <= 0.2]
    best = max(score(d) for d in ok)
    choice = next(d for d in ok if score(d) >= best - 1)
    h1 = score("Lossless federated XGBoost") >= score("Federated XGBoost bagging (Flower)") + 2
    json.dump(dict(choice=choice, best_score=round(best, 2), scores_T1B={d: round(score(d), 2) for d in T.index},
                   eligible=ok, H1_lossless_ge_bagging_plus_2=bool(h1)), open(f"{OUT}/choice.json", "w"), indent=1)
    print("FEVER's detector:", choice, "| H1:", h1)


if __name__ == "__main__":
    {"rows": stage_rows, "central": stage_central, "evaluate": stage_evaluate}[sys.argv[1]]()
