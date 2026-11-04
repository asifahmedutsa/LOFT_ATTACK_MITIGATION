"""Flow hold for v2.1 + PortGuard, second round (follow-up to results/flowhold).

In the first round the hold selected for v2.1 + PortGuard (30 s, first demotion, sticky) failed
HH3: under E9's fast-refresh attack with benign-looking packets DualGuard falsely demotes many
benign flows (796 -> 2,730 benign demotes per episode), and a sticky hold on the first demotion
turns each of them into a flow refused for good (benign harm 2.3 -> 5.0 %, 4.8 points of it
refused by the hold). Selection had looked only at A1-A7, where false demotes are rare.

This round asks whether a hold that needs repeated demotions keeps the load gain without that
cost. Same mechanism and code as round one; only the grid and the selection rule change:

select  v2.1 + PortGuard with hold_s {10, 30, 60} x strikes {2, 3} x {fixed, sticky}, plus
        round one's selection (30 s, strike 1, sticky) for reference, on validation seeds
        2000-2002, D1-D3 and T1, A1-A7 + benign + E9's three selected attacks. Eligible:
        mean benign harm over A1-A7 + benign <= base + 0.25 points AND worst E9 attack's
        mean harm <= base's + 0.5 points (round one's HH3, now part of selection). Among
        eligible: fewest mean flow-mods over A1-A7 (ties within 1 %: lower harm); none
        eligible -> no hold.
test    base and selected hold, fresh seeds 19000-19009, same cells; HH1-HH3 as in round one.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.flowhold2 --stages prereg,select,test,report

Writes results/flowhold2/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import itertools
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import e9_adaptive as E9
from . import flowhold as FH
from . import revision1 as R1
from .config import VARIANTS
from .experiment import SPLITS, _dump
from .report import holm

OUT = "results/flowhold2"
BASE = "v2.1+pg"
TEST_SEEDS = list(range(19000, 19010))
GRID = dict(hold_s=[10.0, 30.0, 60.0], strikes=[2, 3], mode=["fixed", "sticky"])
ROUND1 = "v2.1+pg|hold30s1sticky"
HARM_MARGIN, E9_MARGIN = 0.0025, 0.005
HYPOTHESES = dict(FH.HYPOTHESES)


def _e9():
    return sorted({b["attack"] for b in json.load(open(os.path.join(E9.OUT, "selected.json"))).values()})


def _candidates():
    return [f"{BASE}|{FH._key(h, k, m)}" for h, k, m in itertools.product(*GRID.values())] + [ROUND1]


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=FH.DOMS, grid=GRID,
        reference_candidate=ROUND1, base=BASE, val_seeds=list(SPLITS["val"]),
        test_seeds=TEST_SEEDS, e9_attacks=_e9(),
        load_metric="flow_mods = installs + deletes + demotes per episode",
        selection=f"eligible: mean harm (A1-A7 + benign) <= base + {HARM_MARGIN} and worst E9 "
                  f"attack's mean harm <= base's + {E9_MARGIN}; among eligible, fewest mean "
                  f"flow_mods over A1-A7; ties within 1 %: lower harm; none eligible: no hold",
        test_cells="A1-A7, benign and E9's three selected attacks; dedicated ports",
        hypotheses=HYPOTHESES,
        motivation="round one (results/flowhold) failed HH3 for v2.1 + PortGuard"))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    if not os.path.exists(path):
        FH._load()
        cells = [(d, v, s) for d in FH.DOMS for v in list(VARIANTS) + [None] + _e9()
                 for s in SPLITS["val"]]
        tasks = [("select", n, *c) for n in [BASE] + _candidates() for c in cells]
        FH._run(tasks, workers, "select").to_csv(path, index=False)
    df = pd.read_csv(path)
    std = df[df.variant.isin(list(VARIANTS) + ["benign"])]
    harm = std.groupby("defense").benign_flows_harmed_frac.mean()
    load = df[df.variant.isin(VARIANTS)].groupby("defense").flow_mods.mean()
    e9w = df[~df.variant.isin(list(VARIANTS) + ["benign"])].groupby(
        ["defense", "variant"]).benign_flows_harmed_frac.mean().groupby("defense").max()
    rows = []
    for c in [BASE] + _candidates():
        ok = bool(harm[c] <= harm[BASE] + HARM_MARGIN and e9w[c] <= e9w[BASE] + E9_MARGIN)
        rows.append(dict(defense=c, harm_pct=round(100 * harm[c], 3), e9_worst_pct=round(100 * e9w[c], 2),
                         flow_mods=round(load[c]), eligible=ok and c != BASE))
    t = pd.DataFrame(rows)
    ok = t[t.eligible]
    if len(ok):
        near = ok[ok.flow_mods <= 1.01 * ok.flow_mods.min()]
        sel = near.sort_values("harm_pct").defense.iloc[0]
    else:
        sel = BASE
    t.to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected={BASE: sel}))
    print(t.to_string(index=False))
    print("selected", sel)


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    FH._load()
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"][BASE]
    names = list(dict.fromkeys([BASE, sel]))
    cells = [(d, v, s) for d in FH.DOMS for v in list(VARIANTS) + [None] + _e9() for s in TEST_SEEDS]
    FH._run([("test", n, *c) for n in names for c in cells], workers, "test").to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    s = json.load(open(os.path.join(OUT, "selected.json")))["selected"][BASE]
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    std = list(VARIANTS) + ["benign"]
    df["group"] = np.where(df.variant.isin(VARIANTS), "A1-A7",
                           np.where(df.variant == "benign", "benign", "E9"))
    piv = df.groupby(["group", "defense"])[["benign_flows_harmed_frac", "benign_flows_blocked_frac",
                                            "benign_demotes", "flow_mods", "packet_in"]].mean()
    piv[["benign_flows_harmed_frac", "benign_flows_blocked_frac"]] *= 100
    piv.round(2).to_csv(os.path.join(tdir, "by_group.csv"))
    pd.set_option("display.width", 250)
    print(piv.round(2).to_string())
    if s == BASE:
        print("no hold selected; nothing to test")
        return
    t1a2 = df[(df.domain == "T1") & (df.variant == "A2")].groupby("defense").flow_mods.mean()
    red = 1 - t1a2[s] / t1a2[BASE]
    att = df[df.variant != "benign"]
    tests = [dict(hyp="HH1", metric="flow_mods", **dict(zip(("mean_diff", "a_lower", "a_higher", "p"),
                                                            R1.cluster_wilcoxon(att, "flow_mods", s, BASE))))]
    h = df[df.variant.isin(std)]
    A = h[h.defense == s].set_index(["domain", "variant", "seed"]).benign_flows_harmed_frac
    B = h[h.defense == BASE].set_index(["domain", "variant", "seed"]).benign_flows_harmed_frac
    d = (A - B.reindex(A.index)).values
    upper = FH._boot_upper(d, np.array([f"{i[0]}|{i[1]}" for i in A.index]))
    tests.append(dict(hyp="HH2", metric="harm", **dict(zip(("mean_diff", "a_lower", "a_higher", "p"),
                                                           R1.cluster_wilcoxon(h, "benign_flows_harmed_frac", s, BASE)))))
    e = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()
    ws, wb = 100 * e.loc[s].max(), 100 * e.loc[BASE].max()
    summ = dict(base=BASE, selected=s, t1_a2_flowmod_reduction_pct=round(100 * red, 1),
                HH1_t1a2=bool(red >= 0.30), harm_diff_pct=round(100 * float(d.mean()), 3),
                harm_diff_upper95_pct=round(100 * upper, 3), HH2=bool(upper <= 0.005),
                e9_worst_selected=round(ws, 2), e9_worst_base=round(wb, 2), HH3=bool(ws <= wb + 0.5))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    pd.DataFrame([summ]).to_csv(os.path.join(tdir, "summary.csv"), index=False)
    print(t.round(5).to_string(index=False))
    print(json.dumps(summ, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("select", lambda: stage_select(a.workers)),
                     ("test", lambda: stage_test(a.workers)), ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
