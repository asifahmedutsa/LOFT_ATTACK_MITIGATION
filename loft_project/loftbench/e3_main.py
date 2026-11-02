"""E3 (docs/other_papers_run_plan.md): the main comparison in DMS-BTT's table format, extended
past E2 to 600 s episodes, the bigFlows trace T1 and the fast-refresh attack X1.

E2 compared the published defenses on D1-D3 only, at 300 s, on A1-A7. Here every defense runs
unchanged (E2's knobs, the corrected rDefender, revision 5's T1 models, round one's flow hold
and the eviction fallback, nothing retuned) on D1-D3 and T1 for 600 s, attack from 50 s, on
A1-A7, X1 (E9's best response to six of seven defenses: refresh every 2-3 s, benign sizes,
pooled sources, 1,700 flows) and benign only. SIFT, TableGuard and SFTO-Guard from the plan
are not reimplemented; they are older and their mechanisms are covered by the defenses here.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e3_main --stages prereg,test,report

Fresh seeds 20000-20009, one shot. Writes results/e3_main/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import pickle
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import e2_baselines as E2
from . import e9_adaptive as E9
from . import flowhold as FH
from . import revision1 as R1
from . import revision5 as R5
from . import testbed_baselines as TB
from . import v21
from .baselines import FloRa, FTMaster, FTOP, RDefender
from .config import VARIANTS, SimConfig
from .defenses import DMSBTT, Defense, OVSEvict, PortGuard
from .experiment import _dump
from .report import holm
from .sim import run_episode

OUT = "results/e3_main"
DOMS = ["D1", "D2", "D3", "T1"]
SEEDS = list(range(20000, 20010))
X1 = "t2-3_p1-3_benign_pool_M1700"
CFG = SimConfig(duration=600.0)
PUBLISHED = ["dms-btt", "ftmaster", "ftop", "flora", "rdefender"]
DEFENSES = ["none", "ovs-evict"] + PUBLISHED + ["v2.1", "v2.1+evict", "v2.1+hold", "v2.1+portguard"]
LABEL = {"none": "No defense (REFUSE)", "ovs-evict": "EVICT (OVS)", "dms-btt": "DMS-BTT (2025)",
         "ftmaster": "FTMaster (2023)", "ftop": "FTOP (2024)", "flora": "FloRa (2024)",
         "rdefender": "rDefender (2024)", "v2.1": "FL-DualGuard v2.1",
         "v2.1+evict": "v2.1 + switch eviction", "v2.1+hold": "v2.1 + flow hold",
         "v2.1+portguard": "v2.1 + PortGuard"}
HYPOTHESES = dict(
    E3H1="harm: v2.1 harms fewer benign flows than each published defense over A1-A7 on D1-D3 "
         "and T1 at 600 s (paired cluster Wilcoxon over domain x seed, Holm over the five, "
         "p < 0.05 and lower mean)",
    E3H2="containment: v2.1 leaves the attacker a smaller average table share than each "
         "published defense over A1-A7 (same test)",
    E3H3="adaptive: under X1, v2.1 + PortGuard harms fewer benign flows than every other "
         "defense in the table (same test, Holm over the ten)",
    E3H4="T1: v2.1's A1-A7 harm on T1 is lower than each published defense's (descriptive, "
         "means only: 10 clusters)",
)
_M = {}


def _load():
    FH._load()
    m = pickle.load(open(os.path.join(TB.OUT, "models_t1.pkl"), "rb"))
    _M["t1"] = {k: E2._OneThread(x) for k, x in m.items()}
    _M["rdef"] = json.load(open(os.path.join(E2.OUT, "rdefender_fix", "selected.json")))["selected"]
    _M["hold"] = json.load(open(os.path.join(FH.OUT, "selected.json")))["selected"]["v2.1"]


def _make(name, d):
    if name == "none":
        return Defense()
    if name == "ovs-evict":
        return OVSEvict()
    if name == "rdefender":
        return RDefender(**_M["rdef"])
    if name in ("ftmaster", "ftop", "flora"):
        if d != "T1":
            return E2._make(name, d)
        m, k = _M["t1"], E2._M["knobs"].get(name, {})
        if name == "ftmaster":
            return FTMaster(m["ftmaster_state/T1"], m["ftmaster_rule/T1"], **k)
        if name == "ftop":
            return FTOP(m["ftop_state/T1"], m["ftop_rule/T1"], **k)
        return FloRa(m["flora_rule/T1"], **k)
    if name == "dms-btt":
        m = R5._CTX["m"] if d == "T1" else v21._CTX[0]
        return DMSBTT(m[f"dms_state/{d}"], m[f"dms_flow/{d}"])
    if name == "v2.1+hold":
        df = FH._make(_M["hold"], d)
    elif name == "v2.1+portguard":
        df = FH._make("v2.1+pg", d)
    else:
        df = FH._dg(d)
    if name == "v2.1+evict":
        df.evict_on_full = OVSEvict._evict
    df.name = name
    return df


def _episode(args):
    name, d, v, s = args
    old = FH.CFG
    FH.CFG = CFG                      # _traffic reads the episode length from FH.CFG
    try:
        tr = FH._traffic(d, v, s)
    finally:
        FH.CFG = old
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(defense=name, domain=d, variant=v or "benign", seed=s,
                flow_mods=r["installs"] + r["deletes"] + r["demotes"], **r)


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=DOMS, seeds=SEEDS,
        duration_s=CFG.duration, attack_start_s=CFG.attack_start, defenses=DEFENSES,
        attacks=list(VARIANTS) + [X1, "benign"], x1=X1,
        knobs="E2 selected.json (FloRa, FTMaster, FTOP), rdefender_fix selected.json, DMS-BTT "
              "paper defaults, revision 5 T1 models, flowhold selected.json (v2.1), revision 4b "
              "PortGuard; nothing retuned",
        hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    tasks = [(n, d, v, s) for n in DEFENSES for d in DOMS for v in list(VARIANTS) + [X1, None]
             for s in SEEDS]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [test] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _row(g, b, name):
    fo = g.first_overflow_s.dropna()
    return {"defense": LABEL[name],
            "Avg Pa (%)": round(100 * g.avg_attack_occ_post.mean(), 2),
            "Max Pa (%)": round(100 * g.max_attack_occ.mean(), 2),
            "Avg table usage (%)": round(100 * (g.avg_attack_occ + g.avg_benign_occ).mean(), 2),
            "Earliest overflow (s)": round(fo.mean(), 1) if len(fo) else "never",
            "Runs with overflow (%)": round(100 * g.first_overflow_s.notna().mean(), 1),
            "Overflow after attack (s)": round(g.overflow_seconds_post_attack.mean(), 2),
            "Packet-In": int(g.packet_in.mean()), "TABLE_FULL": int(g.table_full.mean()),
            "Flow-mods": int(g.flow_mods.mean()),
            "Benign harmed (%)": R1._fmt(g, "benign_flows_harmed_frac"),
            "Benign harmed, no attack (%)": round(100 * b.benign_flows_harmed_frac.mean(), 2),
            "Benign Packet-In lost (%)": round(100 * (g.benign_rejected_pkts / g.benign_pkts).mean(), 2),
            "Decision time (ms)": round(g.decision_ms_mean.mean(), 2)}


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    att = df[df.variant.isin(VARIANTS)]
    x1 = df[df.variant == X1]
    ben = df[df.variant == "benign"]
    main = pd.DataFrame([_row(att[att.defense == n], ben[ben.defense == n], n) for n in DEFENSES])
    main.to_csv(os.path.join(tdir, "table_main.csv"), index=False)
    xt = pd.DataFrame([_row(x1[x1.defense == n], ben[ben.defense == n], n) for n in DEFENSES])
    xt.to_csv(os.path.join(tdir, "table_x1.csv"), index=False)
    piv = {}
    for k, col in (("harm", "benign_flows_harmed_frac"), ("share", "avg_attack_occ_post")):
        piv[k] = (df[df.variant != "benign"].pivot_table(index="defense", columns="variant", values=col)
                  * 100).round(2).reindex(DEFENSES)
        piv[k].to_csv(os.path.join(tdir, f"{k}_by_variant.csv"))
    dom = (att.pivot_table(index="defense", columns="domain", values="benign_flows_harmed_frac")
           * 100).round(2).reindex(DEFENSES)
    dom.to_csv(os.path.join(tdir, "harm_by_domain.csv"))
    tests = []
    for hyp, data, metric, a, others in (
            ("E3H1", att, "benign_flows_harmed_frac", "v2.1", PUBLISHED),
            ("E3H2", att, "avg_attack_occ_post", "v2.1", PUBLISHED),
            ("E3H3", x1, "benign_flows_harmed_frac", "v2.1+portguard",
             [n for n in DEFENSES if n != "v2.1+portguard"])):
        rows = []
        for b in others:
            md, w, l, p = R1.cluster_wilcoxon(data, metric, a, b)
            rows.append(dict(hyp=hyp, a=a, b=b, metric=metric, mean_diff=md, a_lower=w, a_higher=l, p=p))
        r = pd.DataFrame(rows)
        r["p_holm"] = holm(r.p.values)
        r["holds"] = (r.p_holm < 0.05) & (r.mean_diff < 0)
        tests.append(r)
    t = pd.concat(tests)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    t1 = dom["T1"]
    h4 = {b: bool(t1["v2.1"] < t1[b]) for b in PUBLISHED}
    verdict = {h: bool(t[t.hyp == h].holds.all()) for h in ("E3H1", "E3H2", "E3H3")}
    verdict["E3H4"] = all(h4.values())
    _dump(OUT, "verdict.json", dict(verdict=verdict, e3h4_t1_harm=t1.to_dict()))
    pd.set_option("display.width", 300)
    print(main.to_string(index=False))
    print(xt.to_string(index=False))
    print(piv["harm"].to_string())
    print(dom.to_string())
    print(t.round(5).to_string(index=False))
    print(json.dumps(verdict))


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
