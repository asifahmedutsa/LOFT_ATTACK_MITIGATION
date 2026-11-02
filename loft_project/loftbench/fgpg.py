"""FloodGuard + PortGuard together, with dedicated and shared ports.

Each module fixes one gap of v2.1: FloodGuard the high-rate floods LA and HA (results/floodguard),
PortGuard E9's adaptive fast-refresh attack (results/e9_adaptive). Neither was tested with the
other, and both were tested mainly with the attacker on its own access port: when benign hosts
share the attacker's port, FloodGuard's A1-A7 harm rose from 0.5 to 3.0 %.

Here FloodGuard(PortGuard(v2.1)) runs against v2.1, v2.1 + FloodGuard and v2.1 + PortGuard, all
with their earlier selected knobs (floodguard/selected.json; revision 4b's PortGuard as in
flowhold), nothing retuned, on D1-D3, 300 s, A1-A7 + LA + HA + E9's three selected attacks +
benign, dedicated and shared ports, fresh seeds 21000-21009, one shot.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.fgpg --stages prereg,test,report

Writes results/fgpg/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import e9_adaptive as E9
from . import flowhold as FH
from . import revision1 as R1
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import FloodGuard
from .e2_repro import ATTACKS
from .experiment import _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/fgpg"
CFG = SimConfig(duration=300.0)
DOMS = ["D1", "D2", "D3"]
SEEDS = list(range(21000, 21010))
SCENARIOS = ["dedicated", "shared"]
DEFENSES = ["v2.1", "v2.1+fg", "v2.1+pg", "v2.1+pg+fg"]
FLOODS = ["LA", "HA"]
NI = 0.005                                     # non-inferiority margin, 0.5 points
HYPOTHESES = dict(
    FP1="floods: over LA and HA, v2.1+pg+fg harms fewer benign flows than v2.1+pg, in each port "
        "scenario (paired cluster Wilcoxon over domain x seed, Holm over the two scenarios)",
    FP2="adaptive: over E9's three attacks, v2.1+pg+fg harms fewer benign flows than v2.1+fg, in "
        "each scenario (same test), and its worst E9 attack's mean harm is <= v2.1+pg's + 0.5 "
        "points",
    FP3="A1-A7: v2.1+pg+fg is non-inferior to v2.1+pg (cluster bootstrap 95 % upper bound of "
        "the mean harm difference <= 0.5 points), in each scenario",
    FP4="benign only: v2.1+pg+fg's mean harm is <= v2.1's + 0.1 points, in each scenario",
)
_M = {}


def _e9():
    return sorted({b["attack"] for b in json.load(open(os.path.join(E9.OUT, "selected.json"))).values()})


def _load():
    FH._load()
    _M["fg"] = json.load(open("results/floodguard/selected.json"))["selected"]


def _make(name, d):
    if name in ("v2.1", "v2.1+pg"):
        return FH._make(name, d)
    inner = FH._make("v2.1+pg" if name == "v2.1+pg+fg" else "v2.1", d)
    return FloodGuard(inner, name=name, **_M["fg"])


def _episode(args):
    name, scen, d, v, s = args
    att = None if v is None else (VARIANTS.get(v) or ATTACKS.get(v) or E9.ATTACKS[v])
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], att, s, CFG.duration,
                                    CFG.attack_start), scen)
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(defense=name, scenario=scen, domain=d, variant=v or "benign", seed=s,
                flow_mods=r["installs"] + r["deletes"] + r["demotes"], **r)


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=DOMS, seeds=SEEDS,
        duration_s=CFG.duration, scenarios=SCENARIOS, defenses=DEFENSES,
        attacks=list(VARIANTS) + FLOODS + _e9() + ["benign"], e9_attacks=_e9(),
        knobs="FloodGuard: results/floodguard/selected.json; PortGuard: revision 4b (as in "
              "flowhold); nesting FloodGuard(PortGuard(v2.1)); nothing retuned",
        hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    tasks = [(n, sc, d, v, s) for n in DEFENSES for sc in SCENARIOS for d in DOMS
             for v in list(VARIANTS) + FLOODS + _e9() + [None] for s in SEEDS]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [test] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    e9 = _e9()
    df["group"] = np.select([df.variant.isin(VARIANTS), df.variant.isin(FLOODS), df.variant.isin(e9)],
                            ["A1-A7", "floods", "E9"], "benign")
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    rows = []
    for (sc, n, g), h in df.groupby(["scenario", "defense", "group"]):
        rows.append(dict(scenario=sc, defense=n, group=g, harmed=R1._fmt(h, "benign_flows_harmed_frac"),
                         attack_share=round(100 * h.avg_attack_occ_post.mean(), 2),
                         overflow_s=round(h.overflow_seconds_post_attack.mean(), 2),
                         flow_mods=int(h.flow_mods.mean())))
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(tdir, "summary.csv"), index=False)
    piv = (df.pivot_table(index=["scenario", "defense"], columns="variant",
                          values="benign_flows_harmed_frac") * 100).round(2)
    piv.to_csv(os.path.join(tdir, "harm_by_variant.csv"))
    tests, checks = [], {}
    for sc in SCENARIOS:
        s = df[df.scenario == sc]
        for hyp, grp, b in (("FP1", "floods", "v2.1+pg"), ("FP2", "E9", "v2.1+fg")):
            md, w, l, p = R1.cluster_wilcoxon(s[s.group == grp], "benign_flows_harmed_frac",
                                              "v2.1+pg+fg", b)
            tests.append(dict(hyp=hyp, scenario=sc, a="v2.1+pg+fg", b=b, mean_diff=md,
                              a_lower=w, a_higher=l, p=p))
        e = s[s.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()
        checks[f"FP2_worst_{sc}"] = dict(pg_fg=round(100 * e.loc["v2.1+pg+fg"].max(), 2),
                                         pg=round(100 * e.loc["v2.1+pg"].max(), 2))
        a = s[s.group == "A1-A7"].set_index(["defense", "domain", "variant", "seed"]).benign_flows_harmed_frac
        d = (a.loc["v2.1+pg+fg"] - a.loc["v2.1+pg"].reindex(a.loc["v2.1+pg+fg"].index))
        up = FH._boot_upper(d.values, np.array([f"{i[0]}|{i[2]}" for i in d.index]))
        checks[f"FP3_{sc}"] = dict(diff=round(100 * float(d.mean()), 3), upper95=round(100 * up, 3))
        b = s[s.group == "benign"].groupby("defense").benign_flows_harmed_frac.mean()
        checks[f"FP4_{sc}"] = dict(pg_fg=round(100 * b["v2.1+pg+fg"], 3), v21=round(100 * b["v2.1"], 3))
    t = pd.DataFrame(tests)
    t["p_holm"] = np.nan
    for hyp in ("FP1", "FP2"):
        m = t.hyp == hyp
        t.loc[m, "p_holm"] = holm(t[m].p.values)
    t["holds"] = (t.p_holm < 0.05) & (t.mean_diff < 0)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    verdict = dict(
        FP1=bool(t[t.hyp == "FP1"].holds.all()),
        FP2=bool(t[t.hyp == "FP2"].holds.all()
                 and all(checks[f"FP2_worst_{sc}"]["pg_fg"] <= checks[f"FP2_worst_{sc}"]["pg"] + 100 * NI
                         for sc in SCENARIOS)),
        FP3=all(checks[f"FP3_{sc}"]["upper95"] <= 100 * NI for sc in SCENARIOS),
        FP4=all(checks[f"FP4_{sc}"]["pg_fg"] <= checks[f"FP4_{sc}"]["v21"] + 0.1 for sc in SCENARIOS))
    _dump(OUT, "verdict.json", dict(verdict=verdict, checks=checks))
    pd.set_option("display.width", 250)
    print(summ.to_string(index=False))
    print(piv.to_string())
    print(t.round(5).to_string(index=False))
    print(json.dumps(dict(verdict=verdict, checks=checks), indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("test", lambda: stage_test(a.workers)),
                     ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
