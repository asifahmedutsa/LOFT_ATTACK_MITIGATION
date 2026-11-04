"""Gate G1 (docs/testbed_plan.md): do our SIFT and TableGuard behave like the papers report?

Neither paper's parameters are stated by the papers we compare against, so each gets a small
grid on validation seeds 2000-2002 (D1-D3 and T1, attacks A1-A3, 300 s, dedicated ports), the
setting with the lowest mean benign harm over those cells is kept, and the gate passes when that
setting harms less than no defense and more than DMS-BTT (the order FTODefender, FTOP and DMS-BTT
report). Rule fixed before the run.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.gate_g1 [--workers 4]

Writes results/gate_g1/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import itertools
import json
from multiprocessing import get_context

import pandas as pd

from . import e3_main as E3
from . import flowhold as FH
from .baselines import SIFT, TableGuard
from .config import SimConfig
from .experiment import SPLITS, _dump
from .sim import run_episode

OUT = "results/gate_g1"
CFG = SimConfig(duration=300.0)
DOMS = ["D1", "D2", "D3", "T1"]
VARS = ["A1", "A2", "A3"]
GRID = {"sift": [dict(q=q, r_low=r) for q, r in itertools.product((0.1, 0.3), (0.2, 1.0))],
        "tableguard": [dict(min_age=a, r_small=r) for a, r in itertools.product((5.0, 20.0), (0.2, 1.0))]}


def _key(fam, kw):
    return fam + "|" + ",".join(f"{k}={v:g}" for k, v in kw.items())


def _make(name, d):
    if "|" not in name:
        return E3._make(name, d)
    fam, args = name.split("|")
    kw = {k: float(v) for k, v in (x.split("=") for x in args.split(","))}
    return (SIFT if fam == "sift" else TableGuard)(**kw)


def _episode(args):
    name, d, v, s = args
    old = FH.CFG
    FH.CFG = CFG
    try:
        tr = FH._traffic(d, v, s)
    finally:
        FH.CFG = old
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(defense=name, domain=d, variant=v, seed=s, harm=r["benign_flows_harmed_frac"],
                attack_share=r["avg_attack_occ_post"], usage=r["avg_attack_occ_post"] + r["avg_benign_occ"],
                overflow_s=r["overflow_seconds_post_attack"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    E3._load()
    names = ["none", "dms-btt"] + [_key(f, kw) for f, g in GRID.items() for kw in g]
    tasks = [(n, d, v, s) for n in names for d in DOMS for v in VARS for s in SPLITS["val"]]
    with get_context("fork").Pool(a.workers) as p:
        df = pd.DataFrame(p.map(_episode, tasks, chunksize=2))
    df.to_csv(os.path.join(OUT, "episodes.csv"), index=False)
    m = df.groupby("defense")[["harm", "attack_share", "usage", "overflow_s"]].mean()
    out = {}
    for fam in GRID:
        sel = m[m.index.str.startswith(fam + "|")].harm.idxmin()
        out[fam] = dict(selected=sel, harm=round(100 * m.harm[sel], 2),
                        passes=bool(m.harm["none"] > m.harm[sel] > m.harm["dms-btt"]))
    out["none_harm"] = round(100 * m.harm["none"], 2)
    out["dms_btt_harm"] = round(100 * m.harm["dms-btt"], 2)
    _dump(OUT, "verdict.json", out)
    pd.set_option("display.width", 200)
    print((m * [100, 100, 100, 1]).round(2).to_string())
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
