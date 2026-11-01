"""E9 (docs/other_papers_run_plan.md): adaptive attackers. Each defense faces the attack that
hurts it most, found by a search with oracle access to that defense (ALFO's attacker adapts to
the eviction policy; ours adapts to every defense).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e9_adaptive --stages prereg,search,test,report

search  72 LFTO settings (refresh period x packets per refresh x packet sizes x source mode x
        flows per attacker) against each defense on validation seeds 2000-2001, D1-D3. The
        attacker's objective is the benign harm of the defended table (ties: attack share).
        Flows per attacker include 600 and 1,000, which keep the table under v2.1's 70 %
        trigger: an attacker that knows the trigger and stays below it.
test    every defense against every defense's best response (the union of selected attacks),
        unused seeds 16000-16009, D1-D3, dedicated ports. Reported: each defense's worst case
        over all selected attacks, and the full matrix.

Writes results/e9_adaptive/.
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

import pandas as pd

from . import e2_baselines as E2
from . import revision1 as R1
from . import v21
from .baselines import RDefender
from .config import DOMAINS, AttackVariant, SimConfig
from .data import DOMAIN_IDX
from .defenses import FloodGuard
from .experiment import _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/e9_adaptive"
SEARCH_SEEDS = [2000, 2001]
TEST_SEEDS = list(range(16000, 16010))
DEFENSES = ["ovs-evict", "dms-btt", "ftop", "rdefender", "v2.1", "v2.1+fg", "v2.1+portguard"]
OURS = ("v2.1", "v2.1+fg", "v2.1+portguard")
GRID = dict(t1=[(2.0, 3.0), (5.0, 8.5), (8.0, 9.8)], pkts=[(1, 1), (1, 3)],
            size=["fixed", "benign"], src=["pool", "spoof"], m=[600, 1000, 1700])
CFG = SimConfig(duration=300.0)
_M = {}


def _key(t1, pkts, size, src, m):
    return f"t{t1[0]:g}-{t1[1]:g}_p{pkts[0]}-{pkts[1]}_{size}_{src}_M{m}"


ATTACKS = {_key(*c): AttackVariant(_key(*c), 100, c[0], max_flows=c[4], pkts_per_refresh=c[1],
                                   size_mode=c[2], src_mode=c[3])
           for c in itertools.product(*GRID.values())}


def _make(name, d):
    if name == "rdefender":
        return RDefender(**_M["rdef"])
    if name == "v2.1+fg":
        return FloodGuard(v21._make("v2.1", d, None), name=name, **_M["fg"])
    return E2._make(name, d)


def _episode(args):
    stage, name, d, a, s = args
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], ATTACKS[a] if a else None, s,
                                    CFG.duration, CFG.attack_start), "dedicated")
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(stage=stage, defense=name, domain=d, attack=a or "benign", seed=s, **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def _load():
    E2._load()
    _M["rdef"] = json.load(open("results/e2_baselines/rdefender_fix/selected.json"))["selected"]
    _M["fg"] = json.load(open("results/floodguard/selected.json"))["selected"]


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), grid={k: v for k, v in GRID.items()},
        n_attacks=len(ATTACKS), defenses=DEFENSES, search_seeds=SEARCH_SEEDS, test_seeds=TEST_SEEDS,
        attacker_objective="max mean benign_flows_harmed_frac over search episodes "
                           "(ties within 0.1 points: higher avg_attack_occ_post)",
        hypotheses=dict(
            H9="v2.1's worst case over all selected attacks is lower than every baseline's "
               "worst case (benign harm, test seeds)",
            H9b="v2.1's harm under its own best-response attack stays below each baseline's harm "
                "under that baseline's own best-response attack, in paired cluster tests",
            H9c="the same two statements for v2.1 + PortGuard and v2.1 + FloodGuard (reported "
                "separately; PortGuard is the fix for fast refresh from revision step 4)")))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_search(workers):
    path = os.path.join(OUT, "search_episodes.csv")
    if not os.path.exists(path):
        _load()
        tasks = [("search", n, d, a, s) for n in DEFENSES for a in ATTACKS for d in DOMAINS
                 for s in SEARCH_SEEDS]
        _run(tasks, workers, "search").to_csv(path, index=False)
    df = pd.read_csv(path)
    g = df.groupby(["defense", "attack"])[["benign_flows_harmed_frac", "avg_attack_occ_post"]].mean()
    best = {}
    for n in DEFENSES:
        h = g.loc[n]
        top = h[h.benign_flows_harmed_frac >= h.benign_flows_harmed_frac.max() - 0.001]
        a = top.avg_attack_occ_post.idxmax()
        best[n] = dict(attack=a, harm=float(h.loc[a, "benign_flows_harmed_frac"]),
                       attack_share=float(h.loc[a, "avg_attack_occ_post"]))
    _dump(OUT, "selected.json", best)
    print(json.dumps(best, indent=1))


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    best = json.load(open(os.path.join(OUT, "selected.json")))
    attacks = sorted({b["attack"] for b in best.values()})
    tasks = [("test", n, d, a, s) for n in DEFENSES for a in attacks for d in DOMAINS
             for s in TEST_SEEDS]
    _run(tasks, workers, "test").to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    best = json.load(open(os.path.join(OUT, "selected.json")))
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    mat = (100 * df.groupby(["defense", "attack"]).benign_flows_harmed_frac.mean()).unstack(1).round(2)
    mat.to_csv(os.path.join(tdir, "harm_matrix.csv"))
    occ = (100 * df.groupby(["defense", "attack"]).avg_attack_occ_post.mean()).unstack(1).round(1)
    occ.to_csv(os.path.join(tdir, "attack_share_matrix.csv"))
    rows = []
    for n in DEFENSES:
        own = df[(df.defense == n) & (df.attack == best[n]["attack"])]
        worst_a = mat.loc[n].idxmax()
        rows.append(dict(defense=n, own_best_attack=best[n]["attack"],
                         harm_own_best=R1._fmt(own, "benign_flows_harmed_frac"),
                         attack_share_own_best=round(100 * own.avg_attack_occ_post.mean(), 1),
                         overflow_s_own_best=round(own.overflow_seconds_post_attack.mean(), 2),
                         worst_attack=worst_a, harm_worst=float(mat.loc[n, worst_a])))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(tdir, "summary.csv"), index=False)
    tests = []
    for n in DEFENSES:
        if n in OURS:
            continue
        for ours in OURS:
            a = df[(df.defense == ours) & (df.attack == best[ours]["attack"])]
            b = df[(df.defense == n) & (df.attack == best[n]["attack"])]
            m = pd.concat([a.assign(defense="ours"), b.assign(defense="base")])
            md, w, l, p = R1.cluster_wilcoxon(m, "benign_flows_harmed_frac", "ours", "base")
            tests.append(dict(ours=ours, baseline=n, mean_diff=md, ours_lower=w, ours_higher=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s.to_string(index=False))
    print(mat.to_string())
    print(t.round(5).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,search,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("search", lambda: stage_search(a.workers)),
                     ("test", lambda: stage_test(a.workers)), ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
