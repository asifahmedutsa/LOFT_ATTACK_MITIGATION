"""FloodGuard: a per-port new-flow rate cap added to FL-DualGuard v2.1 for high-rate floods.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.floodguard_exp --stages prereg,select,test,report

prereg   writes the candidate grid and selection rule before any episode runs
select   validation seeds 2000-2002, D1-D3, A1-A7 + LA + HA + benign, dedicated and shared ports
test     one shot on unused seeds 14000-14009 (main setting, both port scenarios) and
         14000-14004 in rDefender's setting (5,000 entries, idle 30 s): v2.1, v2.1 + FloodGuard,
         rDefender (corrected, as selected in E2's fix)
report   tables

Writes results/floodguard/.
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
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import revision1 as R1
from . import v21
from .baselines import RDefender
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import FloodGuard
from .e2_repro import ATTACKS, RD_CFG
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/floodguard"
MAIN = SimConfig(duration=300.0)
STD = list(VARIANTS)                      # A1-A7
FLOODS = ["LA", "HA"]
SCENARIOS = ["dedicated", "shared"]
TEST_SEEDS = list(range(14000, 14010))
CANDIDATES = dict(mult=[3.0, 5.0, 10.0], r_min=[20.0, 50.0, 100.0], purge=[False, True])
RULE = dict(
    objective="minimise mean benign harm over all attacked validation episodes (A1-A7, LA, HA; "
              "dedicated and shared ports)",
    constraints=dict(avg_attack_occ_post_max=0.15, overflow_seconds_post_attack_max=5.0,
                     benign_only_harmed_max=0.01,
                     a1_a7_harm_vs_v21_max_points=0.5),
    tie_break="within 0.05 points: purge off, then larger mult, then larger r_min (gentler)",
    fallback="if none is feasible: minimise total constraint violation, then the objective",
)
_M = {}


def _attack(v):
    return None if v is None else (ATTACKS[v] if v in ATTACKS else VARIANTS[v])


def _make(name, d, knobs):
    if name == "v2.1":
        return v21._make("v2.1", d, None)
    if name == "v2.1+fg":
        return FloodGuard(v21._make("v2.1", d, None), name=name, **knobs)
    if name == "rdefender":
        return RDefender(**knobs)
    raise ValueError(name)


def _episode(args):
    setting, name, knobs, scen, d, v, s = args
    cfg = MAIN if setting == "main" else RD_CFG
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], _attack(v), s, cfg.duration,
                                    cfg.attack_start), scen)
    r = run_episode(tr, cfg, _make(name, d, knobs), record_ts=False).summary
    return dict(setting=setting, defense=name, knobs=json.dumps(knobs, sort_keys=True),
                scenario=scen, domain=d, variant=v or "benign", seed=s, **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def _load():
    sel = json.load(open("results/v21/selected.json"))["selected"]
    v21._load_ctx("results/v2", "results/v21", sel)


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), candidates=CANDIDATES, rule=RULE,
        validation=dict(seeds=list(SPLITS["val"]), attacks=STD + FLOODS, scenarios=SCENARIOS),
        test=dict(seeds=TEST_SEEDS, rdefender_setting_seeds=TEST_SEEDS[:5],
                  defenses=["v2.1", "v2.1+fg", "rdefender"]),
        hypotheses=dict(
            H1="floods LA and HA, both scenarios: v2.1+fg harms fewer benign flows than v2.1",
            H2="A1-A7, both scenarios: v2.1+fg is non-inferior to v2.1 (<= 0.5 points)",
            H3="benign-only traffic: v2.1+fg harms <= v2.1 + 0.1 points",
            H4="rDefender's setting, HA: v2.1+fg harms fewer benign flows than rDefender"),
        note="Motivated by E2's reproduction of rDefender's setting, where v2.1 harmed 55 % "
             "under the high-rate flood HA."))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    if not os.path.exists(os.path.join(OUT, "preregistration.json")):
        raise SystemExit("run prereg first")
    _load()
    cells = [(sc, d, v, s) for sc in SCENARIOS for d in DOMAINS for v in STD + FLOODS + [None]
             for s in SPLITS["val"]]
    cands = [dict(zip(CANDIDATES, c)) for c in itertools.product(*CANDIDATES.values())]
    tasks = [("main", "v2.1", {}, *c) for c in cells]
    tasks += [("main", "v2.1+fg", k, *c) for k in cands for c in cells]
    df = _run(tasks, workers, "select")
    df.to_csv(os.path.join(OUT, "selection_validation.csv"), index=False)
    att, ben = df[df.variant != "benign"], df[df.variant == "benign"]
    key = ["defense", "knobs"]
    g = att.groupby(key)[["benign_flows_harmed_frac", "avg_attack_occ_post",
                          "overflow_seconds_post_attack"]].mean()
    g = g.join(ben.groupby(key).benign_flows_harmed_frac.mean().rename("benign_only_harmed"))
    std = att[att.variant.isin(STD)].groupby(key).benign_flows_harmed_frac.mean().rename("harm_a1_a7")
    g = g.join(std).reset_index()
    ref = float(g[g.defense == "v2.1"].harm_a1_a7.iloc[0])
    c = RULE["constraints"]
    viol = (np.maximum(g.avg_attack_occ_post - c["avg_attack_occ_post_max"], 0) * 100
            + np.maximum(g.overflow_seconds_post_attack - c["overflow_seconds_post_attack_max"], 0)
            + np.maximum(g.benign_only_harmed - c["benign_only_harmed_max"], 0) * 100
            + np.maximum(g.harm_a1_a7 - ref - c["a1_a7_harm_vs_v21_max_points"] / 100, 0) * 100)
    g["violation"] = viol
    g["feasible"] = viol <= 1e-12
    fg = g[g.defense == "v2.1+fg"].copy()
    kn = fg.knobs.map(json.loads)
    fg["tb"] = list(zip(kn.map(lambda k: k["purge"]), -kn.map(lambda k: k["mult"]),
                        -kn.map(lambda k: k["r_min"])))
    pool = fg[fg.feasible] if fg.feasible.any() else fg[fg.violation <= fg.violation.min() + 1e-12]
    best_h = pool.benign_flows_harmed_frac.min()
    best = pool[pool.benign_flows_harmed_frac <= best_h + 0.0005].sort_values("tb").iloc[0]
    sel = json.loads(best.knobs)
    g.to_csv(os.path.join(OUT, "selection_table.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel, feasible_count=int(fg.feasible.sum()),
                                     v21_validation=g[g.defense == "v2.1"].iloc[0].to_dict(),
                                     validation_metrics=best.drop(labels="tb").to_dict()))
    print(g.drop(columns="violation").round(4).to_string(index=False))
    print("SELECTED", sel)


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    rd = json.load(open("results/e2_baselines/rdefender_fix/selected.json"))["selected"]
    defs = [("v2.1", {}), ("v2.1+fg", sel), ("rdefender", rd)]
    tasks = [("main", n, k, sc, d, v, s) for n, k in defs for sc in SCENARIOS for d in DOMAINS
             for v in STD + FLOODS + [None] for s in TEST_SEEDS]
    tasks += [("rdef", n, k, "dedicated", d, v, s) for n, k in defs for d in DOMAINS
              for v in ["LA", "HA", "A2", "A4", None] for s in TEST_SEEDS[:5]]
    _run(tasks, workers, "test").to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    rows = []
    for (st, sc, n), g in df.groupby(["setting", "scenario", "defense"]):
        for grp, vs in (("A1-A7", STD), ("LA", ["LA"]), ("HA", ["HA"]), ("A2/A4", ["A2", "A4"]),
                        ("benign", ["benign"])):
            h = g[g.variant.isin(vs)]
            if len(h) == 0:
                continue
            rows.append(dict(setting=st, scenario=sc, defense=n, attacks=grp, episodes=len(h),
                             harmed=R1._fmt(h, "benign_flows_harmed_frac"),
                             attack_share=round(100 * h.avg_attack_occ_post.mean(), 2),
                             overflow_s=round(h.overflow_seconds_post_attack.mean(), 2),
                             benign_blocked_pkts=int(h.benign_blocked_pkts.mean())))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(tdir, "summary.csv"), index=False)
    tests = []
    for (st, sc), g in df.groupby(["setting", "scenario"]):
        for grp, vs in (("floods", FLOODS), ("A1-A7", STD), ("HA", ["HA"])):
            h = g[g.variant.isin(vs)]
            if h.variant.nunique() == 0 or len(h[h.defense == "v2.1+fg"]) == 0:
                continue
            for b in ("v2.1", "rdefender"):
                md, w, l, p = R1.cluster_wilcoxon(h, "benign_flows_harmed_frac", "v2.1+fg", b)
                tests.append(dict(setting=st, scenario=sc, attacks=grp, baseline=b,
                                  mean_diff_fg_minus=md, fg_lower=w, fg_higher=l, p=p))
    t = pd.DataFrame(tests)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s.to_string(index=False))
    print(t.round(5).to_string(index=False))


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
