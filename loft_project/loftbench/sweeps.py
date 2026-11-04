"""E6-E8 (docs/other_papers_run_plan.md): table size and idle timeout sweeps, threshold
sensitivity, and benign flash crowds, against the E2 baselines on the same simulator.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.sweeps --stages prereg,e6,e7,e8,report

e6  table size 1,500 / 2,000 / 3,000 / 3,500 / 4,000 at idle 10 s, and idle 20 / 30 s at
    3,500 entries (FTMaster, FloRa, FTShield and rDefender sweep these). Every defense keeps
    its main-setting model and thresholds: v2.1's flag threshold is a benign score quantile
    and its triggers are table fractions, so neither depends on the table size.
    D1-D3, A1-A3 + benign, test seeds 15000-15004, dedicated ports.
e7  v2.1 sensitivity, validation seeds 2000-2002 only (the selected values stay fixed):
    occupancy trigger rho 0.5-0.9 at the 1 % flag budget, and budget 0.5 / 2 / 5 % at
    rho 0.7 (FTMaster 70/80/90 %, FTShield 60/70/80 %, DMS-BTT Pe). D1-D3, A1-A7 + benign.
e8  benign flash crowds (FTOP): three 12 s crowds per 300 s adding 2x or 4x the domain's
    normal new-flow rate from external addresses, without attack, and 2x during A2.
    Test seeds 15000-15009.
report  tables and paired tests in results/sweeps/tables/.

Writes results/sweeps/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import dataclasses
import hashlib
import json
import pickle
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import pandas as pd

from . import e2_baselines as E2
from . import revision1 as R1
from . import v21
from .baselines import RDefender
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DualGuard, FloodGuard
from .experiment import SPLITS, _dump
from .models import threshold_at_fpr
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/sweeps"
SEEDS = list(range(15000, 15010))
BASE = SimConfig(duration=300.0)
E6_CFGS = {f"cap{c}": dict(capacity=c) for c in (1500, 2000, 3000, 3500, 4000)}
E6_CFGS.update({"idle20": dict(idle_timeout=20.0), "idle30": dict(idle_timeout=30.0)})
E6_DEFENSES = ["none", "ovs-evict", "dms-btt", "ftmaster", "ftop", "rdefender", "v2.1"]
E6_ATTACKS = ["A1", "A2", "A3", None]
E7_SETTINGS = [dict(rho=r, budget=0.01) for r in (0.5, 0.6, 0.7, 0.8, 0.9)]
E7_SETTINGS += [dict(rho=0.7, budget=b) for b in (0.005, 0.02, 0.05)]
E8_DEFENSES = E2.TEST_DEFENSES + ["v2.1+fg"]
E8_CELLS = [("flash2", None), ("flash4", None), ("flash2", "A2")]
HYPOTHESES = dict(
    H6="E6: at every table size and idle timeout, v2.1 harms fewer benign flows than each "
       "baseline over A1-A3 (paired over domain x seed clusters, Holm-corrected)",
    H6b="E6: at every setting where the benign traffic alone fits the table (no defense, no "
        "overflow without attack), v2.1 holds the attacker below 15 % of the table on average",
    H7="E7 (descriptive): with rho 0.6-0.8 and budget 0.5-2 %, v2.1 stays within its selection "
       "constraints (attack share <= 0.15, overflow <= 5 s, benign-only harm <= 1 %)",
    H8="E8: under benign flash crowds without attack, v2.1 harms <= 1 % of benign flows and no "
       "more than the best baseline + 0.5 points",
)
_M = {}


def _flash(d, level):
    p = DOMAINS[d]
    return dataclasses.replace(p, flash_events=3, flash_rate=level * p.new_flow_rate,
                               flash_len=12.0)


def _make(name, d, extra):
    if name == "rdefender":
        return RDefender(**_M["rdef"])
    if name == "v2.1+fg":
        return FloodGuard(v21._make("v2.1", d, None), name=name, **_M["fg"])
    if name == "v2.1-sens":
        models, taus, _, sel = v21._CTX
        pol = v21._policy(dict(sel, rho=extra["rho"]))
        return DualGuard(models[sel["detector"]], _M["taus"][(d, extra["budget"])], **pol)
    return E2._make(name, d)


def _episode(args):
    exp, name, extra, cfgkey, flash, d, v, s = args
    cfg = dataclasses.replace(BASE, **E6_CFGS[cfgkey]) if cfgkey else BASE
    prof = _flash(d, int(flash[-1])) if flash else DOMAINS[d]
    tr = assign_ports(build_traffic(prof, DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                                    cfg.duration, cfg.attack_start), "dedicated")
    r = run_episode(tr, cfg, _make(name, d, extra), record_ts=False).summary
    return dict(exp=exp, defense=name, setting=json.dumps(extra, sort_keys=True) if extra else "",
                cfg=cfgkey or "", traffic=flash or "normal", domain=d, variant=v or "benign",
                seed=s, **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def _load(budgets=False):
    E2._load()
    _M["rdef"] = json.load(open("results/e2_baselines/rdefender_fix/selected.json"))["selected"]
    _M["fg"] = json.load(open("results/floodguard/selected.json"))["selected"]
    if budgets:
        models, taus, _, sel = v21._CTX
        data = pickle.load(open("results/v2/datasets.pkl", "rb"))
        m = models[sel["detector"]]
        _M["taus"] = {}
        for d in DOMAINS:
            v = data[("val", d)]
            sc = m.predict_proba(v.X[v.y == 0])
            for b in sorted({x["budget"] for x in E7_SETTINGS}):
                _M["taus"][(d, b)] = threshold_at_fpr(sc, b)
        del data


def _once(path):
    if os.path.exists(path):
        raise SystemExit(f"{path} exists; refusing to rerun (one-shot evaluation)")


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        e6=dict(configs=E6_CFGS, defenses=E6_DEFENSES, attacks=["A1", "A2", "A3", "benign"],
                seeds=SEEDS[:5], domains=list(DOMAINS)),
        e7=dict(settings=E7_SETTINGS, seeds=list(SPLITS["val"]), attacks=list(VARIANTS) + ["benign"]),
        e8=dict(cells=E8_CELLS, defenses=E8_DEFENSES, seeds=SEEDS,
                flash="3 crowds per 300 s, 12 s each, level x normal new-flow rate, external sources"),
        fixed=dict(rdefender="results/e2_baselines/rdefender_fix/selected.json",
                   floodguard="results/floodguard/selected.json",
                   others="results/e2_baselines/selected.json, results/v21/selected.json"),
        hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_e6(workers):
    path = os.path.join(OUT, "e6_episodes.csv")
    _once(path)
    _load()
    tasks = [("e6", n, None, c, None, d, v, s) for c in E6_CFGS for n in E6_DEFENSES
             for d in DOMAINS for v in E6_ATTACKS for s in SEEDS[:5]]
    _run(tasks, workers, "e6").to_csv(path, index=False)


def stage_e7(workers):
    path = os.path.join(OUT, "e7_episodes.csv")
    _once(path)
    _load(budgets=True)
    tasks = [("e7", "v2.1-sens", st, None, None, d, v, s) for st in E7_SETTINGS
             for d in DOMAINS for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
    _run(tasks, workers, "e7").to_csv(path, index=False)


def stage_e8(workers):
    path = os.path.join(OUT, "e8_episodes.csv")
    _once(path)
    _load()
    tasks = [("e8", n, None, None, f, d, v, s) for n in E8_DEFENSES for f, v in E8_CELLS
             for d in DOMAINS for s in SEEDS]
    _run(tasks, workers, "e8").to_csv(path, index=False)


def _row(h, **k):
    return dict(**k, episodes=len(h), harmed=R1._fmt(h, "benign_flows_harmed_frac"),
                attack_share=round(100 * h.avg_attack_occ_post.mean(), 2),
                overflow_s=round(h.overflow_seconds_post_attack.mean(), 2),
                overflow_s_all=round(h.overflow_seconds.mean(), 2))


def stage_report():
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    pd.set_option("display.width", 250)
    p6 = os.path.join(OUT, "e6_episodes.csv")
    if os.path.exists(p6):
        df = pd.read_csv(p6)
        rows, tests = [], []
        for (c, n), g in df.groupby(["cfg", "defense"], sort=False):
            rows.append(_row(g[g.variant != "benign"], cfg=c, defense=n, attacks="A1-A3"))
            rows.append(_row(g[g.variant == "benign"], cfg=c, defense=n, attacks="benign"))
        for c, g in df[df.variant != "benign"].groupby("cfg", sort=False):
            for b in E6_DEFENSES:
                if b != "v2.1":
                    md, w, l, p = R1.cluster_wilcoxon(g, "benign_flows_harmed_frac", "v2.1", b)
                    tests.append(dict(cfg=c, baseline=b, mean_diff_v21_minus=md, v21_lower=w,
                                      v21_higher=l, p=p))
        t = pd.DataFrame(tests)
        t["p_holm"] = holm(t.p.values)
        pd.DataFrame(rows).to_csv(os.path.join(tdir, "e6_summary.csv"), index=False)
        t.to_csv(os.path.join(tdir, "e6_tests.csv"), index=False)
        piv = df[df.variant != "benign"].groupby(["cfg", "defense"], sort=False)
        print("E6 harm % (A1-A3)\n", (100 * piv.benign_flows_harmed_frac.mean()).unstack(1).round(2))
        print("E6 attack share %\n", (100 * piv.avg_attack_occ_post.mean()).unstack(1).round(1))
        print("E6 benign-only overflow s\n", df[df.variant == "benign"].groupby(
            ["cfg", "defense"], sort=False).overflow_seconds.mean().unstack(1).round(1))
        print(t.round(5).to_string(index=False))
    p7 = os.path.join(OUT, "e7_episodes.csv")
    if os.path.exists(p7):
        df = pd.read_csv(p7)
        rows = []
        for st, g in df.groupby("setting", sort=False):
            a, b = g[g.variant != "benign"], g[g.variant == "benign"]
            rows.append(dict(**json.loads(st), harm_attacked=round(100 * a.benign_flows_harmed_frac.mean(), 2),
                             attack_share=round(100 * a.avg_attack_occ_post.mean(), 2),
                             overflow_s=round(a.overflow_seconds_post_attack.mean(), 2),
                             harm_benign_only=round(100 * b.benign_flows_harmed_frac.mean(), 3),
                             a6_harm=round(100 * g[g.variant == "A6"].benign_flows_harmed_frac.mean(), 2),
                             a4_harm=round(100 * g[g.variant == "A4"].benign_flows_harmed_frac.mean(), 2)))
        s = pd.DataFrame(rows)
        s["within_constraints"] = ((s.attack_share <= 15) & (s.overflow_s <= 5)
                                   & (s.harm_benign_only <= 1))
        s.to_csv(os.path.join(tdir, "e7_summary.csv"), index=False)
        print("E7\n", s.to_string(index=False))
    p8 = os.path.join(OUT, "e8_episodes.csv")
    if os.path.exists(p8):
        df = pd.read_csv(p8)
        rows = [_row(g, traffic=f, variant=v, defense=n)
                for (f, v, n), g in df.groupby(["traffic", "variant", "defense"], sort=False)]
        s = pd.DataFrame(rows)
        s.to_csv(os.path.join(tdir, "e8_summary.csv"), index=False)
        tests = []
        for (f, v), g in df.groupby(["traffic", "variant"], sort=False):
            for b in E8_DEFENSES:
                if b != "v2.1":
                    md, w, l, p = R1.cluster_wilcoxon(g, "benign_flows_harmed_frac", "v2.1", b)
                    tests.append(dict(traffic=f, variant=v, baseline=b, mean_diff_v21_minus=md,
                                      v21_lower=w, v21_higher=l, p=p))
        t = pd.DataFrame(tests)
        t["p_holm"] = holm(t.p.values)
        t.to_csv(os.path.join(tdir, "e8_tests.csv"), index=False)
        print("E8\n", s.to_string(index=False))
        print(t.round(5).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,e6,e7,e8,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("e6", lambda: stage_e6(a.workers)),
                     ("e7", lambda: stage_e7(a.workers)), ("e8", lambda: stage_e8(a.workers)),
                     ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
