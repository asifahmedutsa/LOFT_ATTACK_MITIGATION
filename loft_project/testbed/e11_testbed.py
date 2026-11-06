"""E11 on the testbed: the same-data detection benchmark of loftbench/e11_detect.py, scored on
entries recorded on the Ryu testbed (run_testbed --entry-log, defense none, so no defense changes
the traffic and every detector sees identical rows), with the simulator's T1 as reference.

Detectors, as deployed on the testbed (domain T1):
  ensguard       federated RF + CatBoost (results/e3_ens/models.pkl), tau T1 from ens_config.json
  fl-dualguard   the frozen v2.1 MLP, tau from results/v21/exported/v21_T1.json
  ftmaster, ftop, flora   rule detectors trained on T1 (results/testbed_baselines/models_t1.pkl), 0.5
  dms-btt        DMS-BTT flow model trained on T1 (results/revision5/models.pkl), 0.5
  <baseline>@fed mean of the D1-D3 models (results/e2_baselines, results/v2), as in E11

Row sources:
  sim            simulator T1, the same attacks and seeds (all entries of 5 % of polls' rows)
  tb-wall        testbed, features on the controller's real poll times (what was deployed)
  tb-poll        testbed, the same counters on a clock where polls are exactly 1 s apart
                 (testbed/entrylog.py); tb-poll vs tb-wall isolates poll jitter

Operating points: deployed (the threshold each detector runs with on the testbed); sim-fpr1 /
sim-fpr0.1: tau at 1 % / 0.1 % benign on the simulator's T1 validation benign (the transfer the
testbed deployment relies on); tb-fpr0.1: tau at 0.1 % on the testbed's own benign-only
recordings (an oracle ceiling: how separable the testbed rows are).

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/e11_testbed.py [--runs-glob ...] [--seeds ...]

Writes results/e11_testbed/{cells.csv, table.csv, jitter.csv, report.md}.
"""
import argparse
import glob
import json
import os
import pickle
import re
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylog  # noqa: E402
from loftbench.baselines import flora_rule_features, ftmaster_rule_features, ftop_rule_features  # noqa: E402
from loftbench.config import DOMAINS, SimConfig, attack_variant  # noqa: E402
from loftbench.e11_detect import _metrics, _p1  # noqa: E402
from loftbench.models import threshold_at_fpr  # noqa: E402
from loftbench.sim import run_episode  # noqa: E402
from loftbench.trace import TRACE_DOMAIN_IDX, TRACE_DOMAINS  # noqa: E402
from loftbench.traffic import build_traffic  # noqa: E402

OUT = "results/e11_testbed"
EXP = "results/v21/exported"
RULE = {"ftmaster": ftmaster_rule_features, "ftop": ftop_rule_features, "flora": flora_rule_features}
VARS = ["A2", "A4", "E9P"]
SWITCHES = ["s11", "s12", "s13"]
ATTACK_START = 50.0


def detectors():
    """name -> (scorer(rows) -> P(attack), deployed tau)."""
    from loftbench import e2_baselines as E2
    from loftbench import v21
    E2._load()
    ens = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"]
    cfg = json.load(open(os.path.join(EXP, "ens_config.json")))
    t1 = pickle.load(open("results/testbed_baselines/models_t1.pkl", "rb"))
    base = pickle.load(open("results/e2_baselines/models.pkl", "rb"))
    v2m = pickle.load(open("results/v2/models.pkl", "rb"))[0]
    r5 = pickle.load(open("results/revision5/models.pkl", "rb"))[0]
    g = v21._make("v2.1", "D1", None)
    det = {"ensguard": (lambda r: ens.predict_proba(r["X"]), cfg["tau"]["T1"]),
           "fl-dualguard": (lambda r: _p1(g.model, r["X"] if g.feature_idx is None else r["X"][:, g.feature_idx]),
                            json.load(open(os.path.join(EXP, "v21_T1.json")))["tau"])}
    for fam, f in RULE.items():
        det[fam] = ((lambda r, m=t1[f"{fam}_rule/T1"], f=f: _p1(m, f(r["X"]))), 0.5)
        det[fam + "@fed"] = ((lambda r, ms=[base[f"{fam}_rule/{d}"] for d in DOMAINS], f=f:
                              np.mean([_p1(m, f(r["X"])) for m in ms], axis=0)), 0.5)
    det["dms-btt"] = ((lambda r, m=r5["dms_flow/T1"]: _p1(m, r["dms"])), 0.5)
    det["dms-btt@fed"] = ((lambda r, ms=[v2m[f"dms_flow/{d}"] for d in DOMAINS]:
                           np.mean([_p1(m, r["dms"]) for m in ms], axis=0)), 0.5)
    return det


def sim_rows(v, seed, frac=0.05):
    """Simulator T1 rows for one run (all labelled entries of a random 5 % per poll)."""
    cfg = SimConfig(duration=300.0)
    tr = build_traffic(TRACE_DOMAINS["T1"], TRACE_DOMAIN_IDX["T1"],
                       None if v == "benign" else attack_variant(v), seed, cfg.duration, ATTACK_START)
    rng = np.random.default_rng(seed)
    out = {k: [] for k in ("X", "dms", "y", "t", "interval")}

    def collect(t, fids, obs, lab):
        if len(fids):
            m = rng.random(len(fids)) < frac
            out["X"].append(obs["X"][m])
            out["dms"].append(obs["dms"][m])
            out["y"].append(lab[m].astype(np.int8))
            out["t"].append(np.full(m.sum(), t))
            out["interval"].append(np.full(m.sum(), 1.0))
    run_episode(tr, cfg, collect=collect, record_ts=False)
    return {k: np.concatenate(x) for k, x in out.items()}


def sim_val_benign():
    runs = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    parts = [runs[("T1", None, s)] for s in (2000, 2001, 2002)]
    return {"X": np.concatenate([p.X[p.y == 0] for p in parts]),
            "dms": np.concatenate([p.dms[p.y == 0] for p in parts])}


def tb_runs(pattern):
    """(variant, seed, dir) for recorded runs with an entry log."""
    out = []
    for d in sorted(glob.glob(pattern)):
        m = re.search(r"_T1_([A-Za-z0-9]+)_none_s(\d+)$", d)
        if m and os.path.exists(os.path.join(d, "switch_T1_s11_entries.bin")) and \
                os.path.exists(os.path.join(d, "summary.txt")):
            out.append((m[1], int(m[2]), d))
    return out


def concat(parts):
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-glob", default=os.path.expanduser("~/loft-runs/e11tb_T1_*_none_s*"))
    ap.add_argument("--frac", type=float, default=0.05)
    ap.add_argument("--no-sim", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    det = detectors()
    runs = tb_runs(a.runs_glob)
    if not runs:
        raise SystemExit(f"no recorded runs match {a.runs_glob}")
    seeds = sorted({s for _, s, _ in runs})
    print(f"{len(runs)} testbed runs, seeds {seeds}", flush=True)

    # Rows per (source, variant, seed[, switch]).
    rows = {}
    for v, s, d in runs:
        for clock in ("wall", "poll"):
            parts = []
            for sw in SWITCHES:
                b = entrylog.build(d, sw=sw, clock=clock, frac=a.frac, seed=s)
                b["sw"] = np.full(len(b["y"]), sw)
                parts.append(b)
            rows[(f"tb-{clock}", v, s)] = concat(parts)
        print(f"  built {v} s{s}: {len(rows[('tb-wall', v, s)]['y'])} rows, {time.time() - t0:.0f} s", flush=True)
    if not a.no_sim:
        for v in VARS + ["benign"]:
            for s in seeds:
                rows[("sim", v, s)] = sim_rows(v, s)
        print(f"  simulator rows done, {time.time() - t0:.0f} s", flush=True)
    val = sim_val_benign()

    scores = {}
    for name, (fn, _) in det.items():
        scores[(name, "val")] = fn(val)
        for k, r in rows.items():
            scores[(name, k)] = fn(r) if len(r["y"]) else np.zeros(0)
        print(f"  scored {name}, {time.time() - t0:.0f} s", flush=True)

    cells, jit = [], []
    for name, (_, dep_tau) in det.items():
        vb = scores[(name, "val")]
        taus_sim = {"sim-fpr1": threshold_at_fpr(vb, 0.01), "sim-fpr0.1": threshold_at_fpr(vb, 0.001)}
        for src in ("sim", "tb-wall", "tb-poll"):
            ben = [k for k in rows if k[0] == src and k[1] == "benign"]
            taus = dict(deployed=dep_tau, **taus_sim)
            if ben:
                bs = np.concatenate([scores[(name, k)][rows[k]["y"] == 0] for k in ben])
                taus["tb-fpr0.1"] = threshold_at_fpr(bs, 0.001)
            for v in VARS:
                for s in seeds:
                    k = (src, v, s)
                    if k not in rows:
                        continue
                    r, p = rows[k], scores[(name, k)]
                    # Attack rows while the attack runs; every benign row of the run.
                    m = (r["y"] == 0) | (r["t"] > ATTACK_START)
                    if r["y"][m].min() == r["y"][m].max():
                        continue
                    for op, tau in taus.items():
                        cells.append(dict(source=src, detector=name, op=op, variant=v, seed=s, tau=tau,
                                          n_attack=int(r["y"][m].sum()), n_benign=int((r["y"][m] == 0).sum()),
                                          **_metrics(r["y"][m], p[m], tau)))
                    if src == "tb-wall":
                        att = (r["y"] == 1) & (r["t"] > ATTACK_START)
                        for lo, hi in ((0, 1.2), (1.2, 2.5), (2.5, 1e9)):
                            sel = att & (r["interval"] > lo) & (r["interval"] <= hi)
                            if sel.sum():
                                jit.append(dict(detector=name, variant=v, seed=s, interval=f"{lo}-{hi:g}",
                                                n=int(sel.sum()),
                                                recall_sim_fpr0_1=float((p[sel] >= taus_sim["sim-fpr0.1"]).mean()),
                                                recall_deployed=float((p[sel] >= dep_tau).mean()),
                                                score_median=float(np.median(p[sel]))))
    df = pd.DataFrame(cells)
    df.to_csv(os.path.join(OUT, "cells.csv"), index=False)
    cols = ["accuracy", "precision", "recall", "f1", "fpr", "mcc", "auc", "pr_auc"]
    gb = df.groupby(["source", "detector", "op", "variant"])[cols]
    tab = (gb.mean() * 100).round(2).join((gb.std() * 100).round(2), rsuffix="_std")
    tab.to_csv(os.path.join(OUT, "table.csv"))
    pd.DataFrame(jit).to_csv(os.path.join(OUT, "jitter.csv"), index=False)

    L = ["# E11 on the testbed (same rows for every detector)", "",
         f"Generated by `testbed/e11_testbed.py` from {len(runs)} recorded runs (defense none, seeds "
         f"{', '.join(map(str, seeds))}; switches s11-s13) and the simulator's T1 with the same attacks "
         "and seeds. Means over seeds (and, on the testbed, switches pooled per run).", ""]
    for op in ("sim-fpr0.1", "deployed", "tb-fpr0.1"):
        sub = df[df.op == op]
        if sub.empty:
            continue
        L += [f"## Operating point {op}", ""]
        for metric in ("recall", "fpr", "pr_auc"):
            pv = (sub.pivot_table(index="detector", columns=["variant", "source"], values=metric) * 100).round(2)
            L += [f"### {metric} (%)", "", "```", pv.to_string(), "```", ""]
    if jit:
        j = pd.DataFrame(jit).groupby(["detector", "variant", "interval"])[["n", "recall_sim_fpr0_1", "score_median"]].mean().round(3)
        L += ["## Poll jitter (tb-wall, attack rows by the interval since the previous poll)", "", "```",
              j.to_string(), "```", ""]
    open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
