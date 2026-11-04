"""End-to-end experiment pipeline.

    python -m loftbench.experiment --out results/v2 --stages all

Stages: collect -> train -> offline -> online -> report. Seeds for the
train / validation / offline-test / online-test splits are disjoint, so no
run contributes to more than one split. Thresholds are calibrated and policy
knobs tuned on validation runs only.
"""
import os

# One BLAS thread per worker process; multithreaded BLAS across worker
# processes oversubscribes the CPU (measured ~17x slower inference).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import platform
import subprocess
import time
import warnings
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np

from .config import DOMAINS, EXPOSURE, UNSEEN_VARIANTS, VARIANTS, SimConfig
from .data import DOMAIN_IDX, Dataset, collect_run
from .defenses import DMSBTT, DualGuard, OVSEvict, ThresholdLRU
from .features import CONTEXT_FEATURES, FEATURE_NAMES, SOURCE_FEATURES
from .models import (CatWrap, SkWrap, SubsetModel, _DMSFlowAdapter, threshold_at_fpr,
                     train_federated, train_local)
from .sim import Defense, run_episode
from .traffic import build_traffic

SPLITS = {
    "train": range(1000, 1005),
    "val": range(2000, 2003),
    "test_off": range(3000, 3005),
}
ONLINE_SEEDS = range(4000, 4010)
COLLECT_CFG = SimConfig(duration=240.0)
ONLINE_CFG = SimConfig(duration=300.0)
BUDGET = 0.01          # declared benign flag-rate budget for calibration
FED_ROUNDS = 30
EPOCHS = 30

warnings.filterwarnings("ignore", category=FutureWarning)


def _pool(workers):
    return get_context("fork").Pool(workers)


# ----------------------------------------------------------------------------
# collect
# ----------------------------------------------------------------------------
def _collect_task(args):
    split, d, v, s = args
    return split, d, collect_run(d, v, s, COLLECT_CFG)


def stage_collect(out, workers):
    tasks = []
    for split, seeds in SPLITS.items():
        for d in DOMAINS:
            variants = list(VARIANTS) if split == "test_off" else list(EXPOSURE[d])
            for s in seeds:
                for v in variants + [None]:
                    tasks.append((split, d, v, s))
    parts = {}
    with _pool(workers) as p:
        for split, d, ds in p.imap_unordered(_collect_task, tasks):
            parts.setdefault((split, d), []).append(ds)
    data = {k: Dataset.concat(sorted(v, key=lambda x: x.runs[0]["run_id"]))
            for k, v in parts.items()}
    with open(os.path.join(out, "datasets.pkl"), "wb") as f:
        pickle.dump(data, f)
    summary = {f"{s}/{d}": dict(rows=int(len(ds.y)), attack_frac=float(ds.y.mean()),
                                runs=len(ds.runs), state_rows=int(len(ds.state)))
               for (s, d), ds in data.items()}
    _dump(out, "dataset_summary.json", summary)
    return data


# ----------------------------------------------------------------------------
# train
# ----------------------------------------------------------------------------
def _auc_mean(model, data, split="val"):
    from sklearn.metrics import roc_auc_score
    return float(np.mean([roc_auc_score(data[(split, d)].y, model.predict_proba(data[(split, d)].X))
                          for d in DOMAINS]))


def _train_dms(ds, seed=0):
    from catboost import CatBoostClassifier
    st = ds.state
    sm = CatBoostClassifier(loss_function="MultiClass", iterations=300, random_seed=seed,
                            verbose=False, thread_count=4)
    sm.fit(st[:, :2], st[:, 2].astype(int))
    fm = CatBoostClassifier(loss_function="Logloss", iterations=300, random_seed=seed,
                            verbose=False, thread_count=4)
    fm.fit(ds.dms, ds.y)
    return CatWrap(sm), CatWrap(fm)


def _train_svmrf(ds, seed=0, n=6000):
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    r = np.random.default_rng(seed)
    idx = r.choice(len(ds.y), min(n, len(ds.y)), replace=False)
    m = make_pipeline(StandardScaler(), VotingClassifier(
        [("svm", SVC(C=1.0, gamma="scale", probability=True, random_state=seed)),
         ("rf", RandomForestClassifier(100, max_depth=8, random_state=seed, n_jobs=1))],
        voting="soft"))
    m.fit(ds.X[idx], ds.y[idx])
    return SkWrap(m)


def stage_train(out, data):
    t0 = time.time()
    tr = {d: data[("train", d)] for d in DOMAINS}
    models, info = {}, {}
    for d in DOMAINS:
        models[f"local/{d}"] = train_local(tr[d].X, tr[d].y, epochs=EPOCHS)
        models[f"dms_state/{d}"], models[f"dms_flow/{d}"] = _train_dms(tr[d])
        models[f"svmrf/{d}"] = _train_svmrf(tr[d])
    allX = np.concatenate([tr[d].X for d in DOMAINS])
    ally = np.concatenate([tr[d].y for d in DOMAINS])
    models["pooled"] = train_local(allX, ally, epochs=EPOCHS)
    clients = [(tr[d].X, tr[d].y) for d in DOMAINS]
    for name, mu in (("fedavg", 0.0), ("fedprox", 0.01)):
        m, comm, hist = train_federated(
            clients, rounds=FED_ROUNDS, mu=mu,
            log=lambda r, g: dict(round=r + 1, val_auc=_auc_mean(g, data)))
        models[name] = m
        info[name] = dict(comm=comm, history=hist)
    for tag, drop in (("nosrc", SOURCE_FEATURES), ("noctx", CONTEXT_FEATURES)):
        idx = [i for i, f in enumerate(FEATURE_NAMES) if f not in drop]
        m, comm, _ = train_federated([(X[:, idx], y) for X, y in clients],
                                     rounds=FED_ROUNDS, mu=0.01)
        models[f"fedprox_{tag}"] = SubsetModel(m, idx)
    # Per-controller calibration on local benign validation scores.
    taus = {}
    for key in ["pooled", "fedavg", "fedprox", "fedprox_nosrc", "fedprox_noctx"]:
        for d in DOMAINS:
            v = data[("val", d)]
            taus[f"{key}/{d}"] = threshold_at_fpr(models[key].predict_proba(v.X[v.y == 0]), BUDGET)
    for d in DOMAINS:
        v = data[("val", d)]
        for key in (f"local/{d}", f"svmrf/{d}"):
            taus[key] = threshold_at_fpr(models[key].predict_proba(v.X[v.y == 0]), BUDGET)
    info["taus"] = taus
    info["train_seconds"] = time.time() - t0
    with open(os.path.join(out, "models.pkl"), "wb") as f:
        pickle.dump((models, taus), f)
    _dump(out, "train_info.json", info)
    return models, taus


# ----------------------------------------------------------------------------
# offline evaluation
# ----------------------------------------------------------------------------
def _exposure_group(d, v):
    if v in UNSEEN_VARIANTS:
        return "unseen-all"
    return "seen-local" if v in EXPOSURE[d] else "seen-remote"


def stage_offline(out, data, models, taus):
    from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                                 recall_score, roc_auc_score, roc_curve)
    detectors = {
        "local-svmrf": lambda d: (models[f"svmrf/{d}"], taus[f"svmrf/{d}"]),
        "local-mlp": lambda d: (models[f"local/{d}"], taus[f"local/{d}"]),
        "pooled": lambda d: (models["pooled"], taus[f"pooled/{d}"]),
        "fedavg": lambda d: (models["fedavg"], taus[f"fedavg/{d}"]),
        "fedprox": lambda d: (models["fedprox"], taus[f"fedprox/{d}"]),
        "fedprox-nosrc": lambda d: (models["fedprox_nosrc"], taus[f"fedprox_nosrc/{d}"]),
        "dms-btt-flow": lambda d: (_DMSFlowAdapter(models[f"dms_flow/{d}"]), 0.5),
    }
    rows, roc = [], {}
    state_rows = []
    for d in DOMAINS:
        D = data[("test_off", d)]
        vrun = {r["run_id"]: r["variant"] for r in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        is_benign_run = np.array([x is None for x in var])
        for name, get in detectors.items():
            m, tau = get(d)
            p = m.predict_proba(D.dms if name == "dms-btt-flow" else D.X)
            fpr, tpr, _ = roc_curve(D.y, p)
            roc[f"{name}/{d}"] = (fpr[::max(1, len(fpr) // 400)], tpr[::max(1, len(tpr) // 400)])
            for v in VARIANTS:
                mask = (var == v) | (is_benign_run & (D.y == 0))
                yt, pv = D.y[mask], p[mask]
                yp = (pv >= tau).astype(int)
                rows.append(dict(
                    detector=name, domain=d, variant=v, exposure=_exposure_group(d, v),
                    auc=roc_auc_score(yt, pv), tpr_at_1fpr=_tpr_at(yt, pv, 0.01),
                    accuracy=accuracy_score(yt, yp), precision=precision_score(yt, yp, zero_division=0),
                    recall=recall_score(yt, yp, zero_division=0), f1=f1_score(yt, yp, zero_division=0),
                    fpr=float(((yp == 1) & (yt == 0)).sum() / max((yt == 0).sum(), 1))))
        st = D.state
        pred = np.ravel(models[f"dms_state/{d}"].predict(st[:, :2])).astype(int)
        y3 = st[:, 2].astype(int)
        state_rows.append(dict(domain=d, n=int(len(y3)), accuracy=float(accuracy_score(y3, pred)),
                               attack_detection_rate=attack_detection_rate(y3, pred),
                               benign_false_alarm=float(((pred > 0) & (y3 == 0)).sum() / max((y3 == 0).sum(), 1))))
    import pandas as pd
    pd.DataFrame(rows).to_csv(os.path.join(out, "offline_detection.csv"), index=False)
    pd.DataFrame(state_rows).to_csv(os.path.join(out, "offline_dms_state.csv"), index=False)
    with open(os.path.join(out, "roc.pkl"), "wb") as f:
        pickle.dump(roc, f)
    return rows


def attack_detection_rate(y_true, y_pred):
    """DMS-BTT ADR: attack-stage samples (1 or 2) predicted as any attack stage."""
    att = y_true > 0
    return float((y_pred[att] > 0).mean()) if att.any() else float("nan")


def _tpr_at(y, p, fpr_target):
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.interp(fpr_target, fpr, tpr))


# ----------------------------------------------------------------------------
# online evaluation
# ----------------------------------------------------------------------------
_MODELS = None
POLICY = {}   # tuned DualGuard knobs (from tuned_policy.json), shared by all detectors


def make_defense(name, d, models, taus):
    def dg(key, **kw):
        tau_key = key if "/" in key else f"{key}/{d}"
        return DualGuard(models[key], taus[tau_key], name=name, **{**POLICY, **kw})
    table = {
        "none": lambda: Defense(),
        "ovs-evict": lambda: OVSEvict(),
        "threshold-lru": lambda: ThresholdLRU(),
        "dms-btt": lambda: DMSBTT(models[f"dms_state/{d}"], models[f"dms_flow/{d}"]),
        "dg-local-svmrf": lambda: dg(f"svmrf/{d}"),
        "dg-local": lambda: dg(f"local/{d}"),
        "dg-pooled": lambda: dg("pooled"),
        "dg-fedavg": lambda: dg("fedavg"),
        "fl-dualguard": lambda: dg("fedprox"),
        "abl-nosoft": lambda: dg("fedprox", soft=False),
        "abl-nohard": lambda: dg("fedprox", hard=False),
        "abl-nocalib": lambda: DualGuard(models["fedprox"], 0.5, name=name, **POLICY),
        "abl-nosrc": lambda: dg("fedprox_nosrc"),
        "abl-noctx": lambda: dg("fedprox_noctx"),
    }
    d_ = table[name]()
    d_.name = name
    return d_


DEFENSES = ["none", "ovs-evict", "threshold-lru", "dms-btt", "dg-local-svmrf", "dg-local",
            "dg-fedavg", "fl-dualguard", "dg-pooled", "abl-nosoft", "abl-nohard",
            "abl-nocalib", "abl-nosrc", "abl-noctx"]


def _online_task(args):
    name, d, v, s, keep_ts, cfg = args
    models, taus = _MODELS
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       cfg.duration, cfg.attack_start)
    res = run_episode(tr, cfg, make_defense(name, d, models, taus), record_ts=keep_ts)
    row = dict(defense=name, domain=d, variant=v or "benign", seed=s, **res.summary)
    return row, (res.timeseries if keep_ts else None)


def stage_online(out, models, taus, workers, defenses=None, seeds=ONLINE_SEEDS,
                 cfg=ONLINE_CFG, tag="online"):
    global _MODELS, POLICY
    _MODELS = (models, taus)
    tp = os.path.join(out, "tuned_policy.json")
    if os.path.exists(tp):
        t = json.load(open(tp))
        POLICY = dict(rho=t["rho"], t_short=t["t_short"])
    print(f"  DualGuard policy knobs: {POLICY or 'defaults'}", flush=True)
    defenses = defenses or DEFENSES
    tasks = [(n, d, v, s, s == seeds[0], cfg) for n in defenses for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in seeds]
    rows, series = [], {}
    t0 = time.time()
    with _pool(workers) as p:
        for i, (row, ts) in enumerate(p.imap_unordered(_online_task, tasks, chunksize=2)):
            rows.append(row)
            if ts is not None:
                series[(row["defense"], row["domain"], row["variant"])] = ts
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    import pandas as pd
    pd.DataFrame(rows).to_csv(os.path.join(out, f"{tag}_episodes.csv"), index=False)
    with open(os.path.join(out, f"{tag}_timeseries.pkl"), "wb") as f:
        pickle.dump(series, f)
    return rows


def stage_export(out, models, taus):
    """Export FedProx weights + per-domain thresholds for the Ryu testbed."""
    ed = os.path.join(out, "exported")
    os.makedirs(ed, exist_ok=True)
    m = models["fedprox"]
    tp = os.path.join(out, "tuned_policy.json")
    knobs = json.load(open(tp)) if os.path.exists(tp) else {}
    for d in DOMAINS:
        _dump(ed, f"fedprox_{d}.json", dict(
            weights=[w.tolist() for w in m.get_weights()], mean=m.scaler.mean.tolist(),
            std=m.scaler.std.tolist(), tau=taus[f"fedprox/{d}"], features=FEATURE_NAMES,
            rho=knobs.get("rho", 0.5), t_short=int(knobs.get("t_short", 1)),
            h_crit=0.90, target=0.80))


# ----------------------------------------------------------------------------
def _dump(out, name, obj):
    with open(os.path.join(out, name), "w") as f:
        json.dump(obj, f, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def manifest(out, args):
    import catboost
    import pandas
    import sklearn
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except Exception:
        commit, dirty = "unknown", None
    _dump(out, "manifest.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), git_commit=commit, git_dirty=dirty,
        args=vars(args), python=platform.python_version(), platform=platform.platform(),
        numpy=np.__version__, pandas=pandas.__version__, sklearn=sklearn.__version__,
        catboost=catboost.__version__, splits={k: list(v) for k, v in SPLITS.items()},
        online_seeds=list(ONLINE_SEEDS), collect_cfg=COLLECT_CFG.to_dict(),
        online_cfg=ONLINE_CFG.to_dict(), budget=BUDGET, fed_rounds=FED_ROUNDS,
        exposure=EXPOSURE, unseen=UNSEEN_VARIANTS,
        domains={k: str(v) for k, v in DOMAINS.items()},
        variants={k: str(v) for k, v in VARIANTS.items()}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/v2")
    ap.add_argument("--stages", default="all")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    stages = ["collect", "train", "offline", "export", "online", "report"] if args.stages == "all" \
        else args.stages.split(",")
    manifest(args.out, args)
    data = models = taus = None
    if "collect" in stages:
        print("[collect]", flush=True)
        data = stage_collect(args.out, args.workers)
    if data is None and {"train", "offline"} & set(stages):
        data = pickle.load(open(os.path.join(args.out, "datasets.pkl"), "rb"))
    if "train" in stages:
        print("[train]", flush=True)
        models, taus = stage_train(args.out, data)
    if models is None and {"offline", "online", "export"} & set(stages):
        models, taus = pickle.load(open(os.path.join(args.out, "models.pkl"), "rb"))
    if "offline" in stages:
        print("[offline]", flush=True)
        stage_offline(args.out, data, models, taus)
    if "export" in stages:
        stage_export(args.out, models, taus)
    if "online" in stages:
        print("[online]", flush=True)
        stage_online(args.out, models, taus, args.workers)
    if "report" in stages:
        from .report import report
        print("[report]", flush=True)
        report(args.out)


if __name__ == "__main__":
    main()
