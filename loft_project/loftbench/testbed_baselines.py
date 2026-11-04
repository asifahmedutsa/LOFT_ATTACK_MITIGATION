"""E4/E5 (docs/other_papers_run_plan.md): export FTMaster, FTOP, FloRa and rDefender for the
Ryu testbed, with the trace domain T1 (bigFlows) trained the same way as D1-D3 in E2.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.testbed_baselines --stages collect,train,export,parity

collect  T1 table-level rows for the FTMaster and FTOP state detectors: every poll of T1's
         training runs (A1-A3 + benign, seeds 1000-1004, as revision 5 trains DMS-BTT on T1)
train    T1 models with E2's hyperparameters; rule models on revision 5's T1 training rows
export   results/v21/exported/{ftmaster,ftop}_{state,rule}_<D>.json (TreeJSON),
         flora_rule_<D>.json (CatBoost JSON) for D1-D3 and T1, and baselines.json with the
         knobs (E2 selection, rDefender as corrected, FloodGuard as selected)
parity   simulator episodes with the exported JSON models against the original models:
         the summaries must be identical (D1 and T1, A2 and benign)

Writes results/testbed_baselines/ and results/v21/exported/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import time
from multiprocessing import get_context

import numpy as np

from . import e2_baselines as E2
from .baselines import (FloRa, FTMaster, FTOP, RDefender, flora_rule_features,
                        ftmaster_rule_features, ftmaster_table_features, ftop_rule_features,
                        ftop_table_features)
from .cbjson import CatBoostJSON
from .cbjson import export as cb_export
from .config import VARIANTS
from .data import Dataset, profile_of
from .experiment import COLLECT_CFG, SPLITS, _dump
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic
from .treejson import TreeJSON
from .treejson import export as tree_export

OUT = "results/testbed_baselines"
EXP = "results/v21/exported"
LIB = ["A1", "A2", "A3"]
DOMS = ["D1", "D2", "D3", "T1"]


def _collect_task(args):
    t, v, s = args
    prof, idx = profile_of(t)
    tr = build_traffic(prof, idx, VARIANTS[v] if v else None, s, COLLECT_CFG.duration,
                       COLLECT_CFG.attack_start)
    rows = []

    def hook(tt, fids, obs, lab):
        on = v is not None and any(a <= tt <= b + 1e-9 for a, b in tr.attack_active)
        rows.append(np.r_[ftmaster_table_features(tt, obs, tr.flow_src), ftop_table_features(obs),
                          int(on)])

    run_episode(tr, COLLECT_CFG, collect=hook, record_ts=False)
    return np.array(rows, np.float32)


def stage_collect(workers):
    tasks = [("T1", v, s) for v in LIB + [None] for s in SPLITS["train"]]
    with get_context("fork").Pool(workers) as p:
        T = np.concatenate(p.map(_collect_task, tasks))
    pickle.dump(T, open(os.path.join(OUT, "t1_table.pkl"), "wb"))
    print("T1 table rows", T.shape, "attack fraction", round(float(T[:, -1].mean()), 3))


def _rule_t1():
    runs = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    return Dataset.concat([runs[("T1", v, s)] for v in LIB + [None] for s in SPLITS["train"]])


def stage_train():
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    T = pickle.load(open(os.path.join(OUT, "t1_table.pkl"), "rb"))
    tr = _rule_t1()
    t0 = time.time()
    m = {"ftmaster_state/T1": XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4,
                                            random_state=0).fit(T[:, :8], T[:, -1]),
         "ftmaster_rule/T1": XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4,
                                           random_state=0).fit(ftmaster_rule_features(tr.X), tr.y),
         "ftop_state/T1": RandomForestClassifier(100, n_jobs=4, random_state=0).fit(T[:, 8:12], T[:, -1]),
         "ftop_rule/T1": RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=0).fit(
             ftop_rule_features(tr.X), tr.y),
         "flora_rule/T1": CatBoostClassifier(iterations=300, random_seed=0, verbose=False,
                                             thread_count=4).fit(flora_rule_features(tr.X), tr.y)}
    pickle.dump(m, open(os.path.join(OUT, "models_t1.pkl"), "wb"))
    _dump(OUT, "train_info.json", dict(table_rows=int(len(T)), table_attack_frac=float(T[:, -1].mean()),
                                      rule_rows=int(len(tr.y)), seconds=round(time.time() - t0, 1)))


def _models():
    m = pickle.load(open(os.path.join(E2.OUT, "models.pkl"), "rb"))
    m.update(pickle.load(open(os.path.join(OUT, "models_t1.pkl"), "rb")))
    return m


def stage_export():
    m = _models()
    tab = pickle.load(open(os.path.join(E2.OUT, "table_data.pkl"), "rb"))
    tab["T1"] = pickle.load(open(os.path.join(OUT, "t1_table.pkl"), "rb"))
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    rule = {d: data[("val", d)].X for d in ("D1", "D2", "D3")}
    del data
    rule["T1"] = _rule_t1().X
    rng = np.random.default_rng(0)
    err = {}
    for d in DOMS:
        T = tab[d][rng.choice(len(tab[d]), min(3000, len(tab[d])), replace=False)]
        X = rule[d][rng.choice(len(rule[d]), 3000, replace=False)]
        for k, Z in ((f"ftmaster_state/{d}", T[:, :8]), (f"ftmaster_rule/{d}", ftmaster_rule_features(X)),
                     (f"ftop_state/{d}", T[:, 8:12]), (f"ftop_rule/{d}", ftop_rule_features(X))):
            err[k] = tree_export(m[k], os.path.join(EXP, k.replace("/", "_") + ".json"), Z)
        p = os.path.join(EXP, f"flora_rule_{d}.json")
        cb_export(m[f"flora_rule/{d}"], p)
        Z = flora_rule_features(X)
        err[f"flora_rule/{d}"] = float(np.abs(CatBoostJSON(p).predict_proba(Z)[:, 1]
                                              - m[f"flora_rule/{d}"].predict_proba(Z)[:, 1]).max())
    knobs = json.load(open(os.path.join(E2.OUT, "selected.json")))["selected"]
    cfg = dict(flora=knobs["flora"], ftmaster=knobs["ftmaster"], ftop=knobs["ftop"],
               rdefender=json.load(open(os.path.join(E2.OUT, "rdefender_fix", "selected.json")))["selected"],
               floodguard=json.load(open("results/floodguard/selected.json"))["selected"],
               source="results/e2_baselines/selected.json, rdefender_fix/selected.json, "
                      "results/floodguard/selected.json; models: loftbench.testbed_baselines")
    json.dump(cfg, open(os.path.join(EXP, "baselines.json"), "w"), indent=2)
    _dump(OUT, "export_parity.json", err)
    print("max parity error", max(err.values()), json.dumps(cfg))


def _make(name, d, js):
    if name == "rdefender":
        return RDefender(**json.load(open(os.path.join(EXP, "baselines.json")))["rdefender"])
    def load(k):
        return TreeJSON(os.path.join(EXP, k + ".json")) if js else _M["/".join(k.rsplit("_", 1))]

    if name == "ftmaster":
        return FTMaster(load(f"ftmaster_state_{d}"), load(f"ftmaster_rule_{d}"))
    if name == "ftop":
        return FTOP(load(f"ftop_state_{d}"), load(f"ftop_rule_{d}"))
    if name == "flora":
        k = json.load(open(os.path.join(EXP, "baselines.json")))["flora"]
        mdl = CatBoostJSON(os.path.join(EXP, f"flora_rule_{d}.json")) if js else _M[f"flora_rule/{d}"]
        return FloRa(mdl, **k)
    raise ValueError(name)


_M = {}


def _parity_task(args):
    name, d, v, js = args
    prof, idx = profile_of(d)
    cfg = E2.SimConfig(duration=300.0)
    tr = assign_ports(build_traffic(prof, idx, VARIANTS[v] if v else None, 4100, cfg.duration,
                                    cfg.attack_start), "dedicated")
    return (name, d, v, js), run_episode(tr, cfg, _make(name, d, js), record_ts=False).summary


def stage_parity(workers):
    _M.update({k: E2._OneThread(x) for k, x in _models().items()})
    tasks = [(n, d, v, js) for n in ("ftmaster", "ftop", "flora") for d in ("D1", "T1")
             for v in ("A2", None) for js in (False, True)]
    with get_context("fork").Pool(workers) as p:
        res = dict(p.map(_parity_task, tasks))
    keys = ("benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds", "deletes", "demotes")
    out, ok = [], True
    for n, d, v, js in tasks:
        if js:
            a, b = res[(n, d, v, False)], res[(n, d, v, True)]
            same = all(a[k] == b[k] for k in keys)
            ok &= same
            out.append(dict(defense=n, domain=d, variant=v or "benign", identical=same,
                            **{k: [a[k], b[k]] for k in keys}))
    _dump(OUT, "sim_parity.json", dict(all_identical=ok, runs=out))
    for r in out:
        print(r["defense"], r["domain"], r["variant"], r["identical"],
              round(100 * r["benign_flows_harmed_frac"][1], 2), r["deletes"])
    print("ALL IDENTICAL" if ok else "MISMATCH")


def stage_crossenv():
    """The controller's build_defense under the testbed's Python 3.8 with the exported models,
    against the original models here, on the same recorded snapshots (D1 and T1, A2, no
    defense, polls 40-200 s). Every poll's deletions and demotions must be identical."""
    import subprocess
    _M.update({k: E2._OneThread(x) for k, x in _models().items()})
    scratch = os.environ.get("LOFT_SCRATCH", OUT)
    names = ["ftmaster", "ftop", "flora", "rdefender"]
    report = {}
    for d in ("D1", "T1"):
        prof, idx = profile_of(d)
        cfg = E2.SimConfig(duration=200.0)
        tr = assign_ports(build_traffic(prof, idx, VARIANTS["A2"], 4100, cfg.duration,
                                        cfg.attack_start), "dedicated")
        snaps = []

        def hook(t, fids, obs, lab):
            if t >= 40:
                snaps.append({k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in obs.items()})

        run_episode(tr, cfg, collect=hook, record_ts=False)
        z = {"n_polls": len(snaps), "capacity": cfg.capacity, "flow_src": tr.flow_src,
             "flow_port": tr.flow_port,
             "meta": json.dumps([dict(t=float(o["t"]), count=int(o["count"]),
                                      table_full_last=int(o["table_full_last"])) for o in snaps])}
        for i, o in enumerate(snaps):
            for k in ("fids", "pkts", "bytes", "install_t", "X"):
                z[f"{i}_{k}"] = o[k]
        snap = os.path.join(scratch, f"snap_{d}.npz")
        np.savez(snap, **z)
        out = os.path.join(scratch, f"testbed_decisions_{d}.npz")
        subprocess.check_call([os.path.expanduser("~/ryu-env/bin/python"), "testbed/check_defenses.py",
                               snap, EXP, d, out, *names])
        got = np.load(out)
        for n in names:
            dfn = _make(n, d, False)
            dfn.reset({"n_flows": len(tr.flow_src), "flow_src": tr.flow_src, "flow_port": tr.flow_port})
            same, acts = True, 0
            for i, o in enumerate(snaps):
                dels, dems = dfn.on_poll(o["t"], dict(o))
                for tag, arr in (("del", dels), ("dem", dems)):
                    a = np.sort(np.asarray([] if arr is None else arr, np.int64))
                    acts += len(a)
                    same &= np.array_equal(a, got[f"{n}|{i}|{tag}"])
            report[f"{n}/{d}"] = dict(identical=bool(same), polls=len(snaps), actions=int(acts))
            print(n, d, report[f"{n}/{d}"], flush=True)
    _dump(OUT, "crossenv_parity.json", report)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="collect,train,export,parity")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("collect", lambda: stage_collect(a.workers)), ("train", stage_train),
                     ("export", stage_export), ("parity", lambda: stage_parity(a.workers)),
                     ("crossenv", stage_crossenv)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()


if __name__ == "__main__":
    main()
