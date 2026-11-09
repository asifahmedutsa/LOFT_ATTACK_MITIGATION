"""Retrained baselines against their earlier (simulator-trained) models on the testbed T1B test
recordings, and the replacement rule of docs/baselines_fidelity_plan.md.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_fidelity   # results/testbed_baselines_tb/fidelity.*
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import gc  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import re  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import tbfl_train_baselines as TT  # noqa: E402
from .baselines import (FTODefender, flora_rule_features, ftmaster_rule_features, ftod_rule_features,  # noqa: E402
                        ftop_rule_features)
from .cbjson import CatBoostJSON  # noqa: E402
from .data import Dataset  # noqa: E402
from .lgbjson import LGBMLRJSON  # noqa: E402
from .tbfl import OUT, RUNS, TAG, TEST  # noqa: E402
from .treejson import TreeJSON  # noqa: E402

TT.BSCALE["T1B"] = 0.5                       # the test recordings' benign scale (record_tbtrain.sh)
STD = ["A1", "A2", "A3", "A5", "A7"]          # G1-G3, Spoof, Pulse
OTHER = ["A4", "A6", "E9P"]                   # Mimic, Slow, Aware
NAMES = {"A1": "G1", "A2": "G2", "A3": "G3", "A4": "Mimic", "A5": "Spoof", "A6": "Slow", "A7": "Pulse",
         "E9P": "Aware"}
SOURCES = {"earlier (simulator T1A)": "results/v21/exported", "retrained, C3": f"{OUT}/baselines_tb/c3",
           "retrained, C1-C3 pooled": f"{OUT}/baselines_tb/pool"}
DST = "results/testbed_baselines_tb"
# (baseline, model, unit, file, features, decision)
MODELS = [
    ("FTMaster", "state", "poll", "ftmaster_state", lambda T: T[:, TT.FTM], lambda m, Z: np.ravel(m.predict(Z)) == 1),
    ("FTMaster", "rule", "entry", "ftmaster_rule", lambda d: ftmaster_rule_features(d.X), lambda m, Z: _p1(m, Z) >= 0.5),
    ("FTOP", "state", "poll", "ftop_state", lambda T: T[:, TT.FTOP], lambda m, Z: np.ravel(m.predict(Z)) == 1),
    ("FTOP", "rule", "entry", "ftop_rule", lambda d: ftop_rule_features(d.X), lambda m, Z: _p1(m, Z) >= 0.5),
    ("FloRa", "rule", "entry", "flora_rule", lambda d: flora_rule_features(d.X), lambda m, Z: _p1(m, Z) >= 0.5),
    ("DMS-BTT", "state", "poll", "dmsB_state", lambda T: T[:, [TT.FN, TT.APIT]], lambda m, Z: np.ravel(m.predict(Z)) != 0),
    ("DMS-BTT", "flow", "entry", "dmsB_flow", lambda d: d.dms, lambda m, Z: _p1(m, Z) >= 0.7),
    ("FTODefender", "rule", "entry", "ftod_rule", lambda d: ftod_rule_features(d.X), lambda m, Z: _p1(m, Z) >= 0.5),
    ("FTODefender", "detector", "poll", "ftod_config", None, None),
]


def _p1(m, Z):
    p = np.asarray(m.predict_proba(Z))
    return p[:, 1] if p.ndim == 2 else p


def _load(path, name):
    if name.startswith(("dmsB", "flora")):
        return CatBoostJSON(path)
    if name == "ftod_rule":
        return LGBMLRJSON(path)
    return TreeJSON(path)


def _ftod_flags(path, polls):
    """FTODefender's detector on each run's polls: DS below th1 (its paper's detection)."""
    from .ftodefender import _features
    c = json.load(open(path))
    sc = FTODefender(None, None, np.array(c["weights"]), np.array(c["fmax"]), np.array(c["fmin"])).score
    return np.concatenate([np.array([sc(f) for f in _features(TT._ftod_seq(a), np.array(c["benchmark"]),
                                                               c["eps"])[:, :3]]) < c["th1"] for a in polls])


def main():
    os.makedirs(DST, exist_ok=True)
    pat = re.compile(rf"{TAG}_T1B_(A\d|E9P|benign)_none_s(\d+)$")
    tasks = [(d, "T1B", m.group(1), int(m.group(2))) for d in sorted(glob.glob(os.path.join(RUNS, f"{TAG}_T1B_*")))
             for m in [pat.search(os.path.basename(d))] if m and int(m.group(2)) in TEST]
    with get_context("fork").Pool(4) as p:
        tab = dict(p.map(TT._table, tasks, chunksize=1))
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    vs = [None] + STD + OTHER
    ent = {v: Dataset.concat([runs[("T1B", v, s)] for s in TEST]) for v in vs}
    del runs
    gc.collect()
    polls = {v: [tab[("T1B", v, s)][sw] for s in TEST for sw in TT.SWITCHES] for v in vs}
    rows = []
    for base, model, unit, fname, feat, decide in MODELS:
        for src, d in SOURCES.items():
            path = os.path.join(d, f"{fname}_T1B.json")
            if not os.path.exists(path):
                continue
            r = dict(baseline=base, model=model, unit=unit, source=src)
            if fname == "ftod_config":
                f = {v: _ftod_flags(path, polls[v]) for v in vs}
                lab = {v: np.concatenate([a[:, TT.ON] for a in polls[v]]) == 1 for v in vs}
            else:
                m = _load(path, fname)
                if unit == "poll":
                    f = {v: decide(m, feat(np.concatenate(polls[v]))) for v in vs}
                    lab = {v: np.concatenate(polls[v])[:, TT.ON] == 1 for v in vs}
                else:
                    f = {v: decide(m, feat(ent[v])) for v in vs}
                    lab = {v: ent[v].y == 1 for v in vs}
                del m
            r["false_alarms"] = 100 * float(f[None].mean())
            r["recall_standard"] = 100 * float(np.concatenate([f[v][lab[v]] for v in STD]).mean())
            for v in STD + OTHER:
                r[NAMES[v]] = 100 * float(f[v][lab[v]].mean())
            rows.append(r)
            print(base, model, src, round(r["false_alarms"], 2), round(r["recall_standard"], 2), flush=True)
            gc.collect()
    df = pd.DataFrame(rows)
    df.round(3).to_csv(f"{DST}/fidelity.csv", index=False)
    write(df, {k: (len(ent[k].y), int((ent[k].y == 1).sum())) for k in vs},
          {k: (sum(len(a) for a in polls[k]), int(sum(a[:, TT.ON].sum() for a in polls[k]))) for k in vs})


def write(df, ent_n, poll_n):
    E, C, P = SOURCES
    dec, L = {}, []
    for b in dict.fromkeys(df.baseline):
        g = df[df.baseline == b]
        checks = []
        for model in dict.fromkeys(g.model):
            h = g[g.model == model].set_index("source")
            if C not in h.index:
                continue
            new = h.loc[C]
            fa_ok = new.false_alarms <= 1.0
            rc_ok = E not in h.index or new.recall_standard >= h.loc[E].recall_standard - 5
            checks.append((model, rc_ok, fa_ok, E in h.index))
        earlier = all(c[3] for c in checks)
        ok = all(c[1] and c[2] for c in checks)
        dec[b] = ("retrained (C3)" if ok or not earlier else "earlier (simulator)", checks, earlier)
    cols = ["false_alarms", "recall_standard"] + [NAMES[v] for v in STD + OTHER]
    L += ["# Retrained baselines against their earlier models (testbed, T1B test recordings)", "",
          "docs/baselines_fidelity_plan.md, fixed before scoring; loftbench/tbfl_fidelity.py. Seeds 4176-4178,",
          "all three switches. Each model at the decision its defense applies. Entry models: 5 % of the entries",
          "per poll; poll models: every poll, labelled by the attack's schedule, without the defenses' occupancy",
          "gates (so poll false alarms are an upper bound). Percentages.", "",
          "| Baseline | Model | Unit | Training | False alarms | Recall, standard | " +
          " | ".join(NAMES[v] for v in STD + OTHER) + " |",
          "|---|---|---|---|---|---|" + "---|" * len(STD + OTHER)]
    for _, r in df.iterrows():
        L.append(f"| {r.baseline} | {r.model} | {r.unit} | {r.source} | " +
                 " | ".join(f"{r[c]:.2f}" for c in cols) + " |")
    L += ["", "## Replacement rule (main arm)", "",
          "| Baseline | Model | Recall >= earlier - 5 | False alarms <= 1 % | Decision |", "|---|---|---|---|---|"]
    for b, (d, checks, earlier) in dec.items():
        for i, (model, rc, fa, has) in enumerate(checks):
            L.append(f"| {b} | {model} | {('yes' if rc else 'no') if has else 'no earlier model'} | "
                     f"{'yes' if fa else 'no'} | {d if i == 0 else ''} |")
    pool_bad = df[(df.source == P) & (df.false_alarms > 1.0)]
    L += ["", "## Data-matched arm (pooled)", "",
          "Not replaced (docs/baselines_fidelity_plan.md). Models above 1 % false alarms: " +
          (", ".join(f"{r.baseline} {r.model} ({r.false_alarms:.2f} %)" for _, r in pool_bad.iterrows()) or "none") + ".",
          "", "## Rows", "", "| Traffic | Entry rows (attack) | Polls (active) |", "|---|---|---|"]
    for k in ent_n:
        L.append(f"| {NAMES.get(k, 'benign') if k else 'benign'} | {ent_n[k][0]} ({ent_n[k][1]}) | "
                 f"{poll_n[k][0]} ({poll_n[k][1]}) |")
    open(f"{DST}/fidelity.md", "w").write("\n".join(L) + "\n")
    json.dump({b: d for b, (d, _, _) in dec.items()}, open(f"{DST}/fidelity_decision.json", "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
