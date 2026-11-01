"""Flow hold for FL-DualGuard (follow-up to the testbed's E5).

On the Ryu testbed (results/testbed_e5) DualGuard demoted attack entries but let them straight
back in: every refresh of a demoted flow cost the controller a Packet-In and a flow-mod. Under
A2 on T1 it sent about twice the flow-mods of DMS-BTT and FTMaster, whose blocklists refuse a
flagged flow at admission, and every new connection's setup delay grew to 10-24 s. The
simulator shows the same gap in its counters (revision 5: 118k vs 47k installs on T1 A2) but
has no controller latency, so the load is measured here as flow-mods sent to the switch
(installs + deletes + demotes) and Packet-Ins.

The fix (DualGuard(hold_s, strikes, sticky)): a flow demoted for the strikes-th time is refused
re-admission for hold_s seconds, its packets dropped at the controller; a sticky hold is renewed
by every refused packet, so the flow is released only after hold_s seconds of silence.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.flowhold --stages prereg,select,test,report

select  hold_s {10, 30, 60} x strikes {1, 2} x {fixed, sticky} under v2.1 and v2.1 + PortGuard, on validation
        seeds 2000-2002, D1-D3 and T1, A1-A7 + benign. Per base, the setting with the fewest
        flow-mods under attack among those whose mean benign harm is at most the base's
        + 0.25 points (ties within 1 %: lower harm); none eligible -> no hold.
test    bases, selected holds and DMS-BTT + blocklist, fresh seeds 18000-18009, the same
        cells plus E9's three best-response attacks. Writes results/flowhold/.
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

from . import e2_baselines as E2
from . import e9_adaptive as E9
from . import revision1 as R1
from . import revision5 as R5
from . import v21
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX, profile_of
from .defenses import DMSBTT, PortGuard
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/flowhold"
DOMS = ["D1", "D2", "D3", "T1"]
TEST_SEEDS = list(range(18000, 18010))
BASES = ["v2.1", "v2.1+pg"]
GRID = dict(hold_s=[10.0, 30.0, 60.0], strikes=[1, 2], mode=["fixed", "sticky"])
HARM_MARGIN = 0.0025
CFG = SimConfig(duration=300.0)
HYPOTHESES = dict(
    HH1="load: each selected hold sends fewer flow-mods than its base under attack (A1-A7 and "
        "E9's attacks; paired cluster Wilcoxon, Holm), and at least 30 % fewer on T1 A2, the "
        "testbed case",
    HH2="harm: each selected hold is non-inferior to its base over A1-A7 + benign (cluster "
        "bootstrap 95 % upper bound of the mean harm difference <= 0.5 points)",
    HH3="adaptive: each selected hold's worst case over E9's attacks is at most its base's "
        "+ 0.5 points",
)


def _key(h, k, m):
    return f"hold{h:g}s{k}" + ("sticky" if m == "sticky" else "")


def _with_hold(dg, hold_s, strikes, sticky=False):
    """Attach a flow hold to a built DualGuard (before any wrapper reads its admit_filter)."""
    dg.hold_s, dg.strikes, dg.sticky = hold_s, strikes, sticky
    if hold_s > 0:
        dg.admit_filter = dg._admit_hold
    return dg


def _dg(d):
    return R5.make("v2.1", d) if d == "T1" else v21._make("v2.1", d, None)


def _make(name, d):
    """name: v2.1 | v2.1+pg | <base>|hold<h>s<k> | dms-blocklist."""
    if name == "dms-blocklist":
        B = R5._CTX["B"]
        m = R5._CTX["m"] if d == "T1" else v21._CTX[0]
        st, fl = (f"dms_state/{d}", f"dms_flow/{d}")
        return DMSBTT(m[st], m[fl], h1=B["h1"], h2=B["h2"], p_thresh=B["p"], numb_mode=B["numb"],
                      blocklist_s=B["block"])
    base, _, hold = name.partition("|")
    dg = _dg(d)
    if hold:
        sticky = hold.endswith("sticky")
        h, k = hold[4:].removesuffix("sticky").split("s")
        _with_hold(dg, float(h), int(k), sticky)
    if base == "v2.1":
        dg.name = name
        return dg
    if base == "v2.1+pg":
        P = R5._CTX["P"]
        return PortGuard(dg, name=name, **{x: P[x] for x in ("mode", "share", "q", "rho_q",
                                                              "hold_s", "tau_s")})
    raise ValueError(name)


def _traffic(d, v, s):
    prof, idx = profile_of(d) if d == "T1" else (DOMAINS[d], DOMAIN_IDX[d])
    att = None if v is None else (VARIANTS[v] if v in VARIANTS else E9.ATTACKS[v])
    return assign_ports(build_traffic(prof, idx, att, s, CFG.duration, CFG.attack_start),
                        "dedicated")


def _episode(args):
    stage, name, d, v, s = args
    r = run_episode(_traffic(d, v, s), CFG, _make(name, d), record_ts=False).summary
    return dict(stage=stage, defense=name, domain=d, variant=v or "benign", seed=s,
                flow_mods=r["installs"] + r["deletes"] + r["demotes"], **r)


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
    R5._load("results/revision5", "results/revision2", "results/revision4b")


def _candidates():
    return [f"{b}|{_key(h, k, m)}" for b in BASES for h, k, m in itertools.product(*GRID.values())]


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=DOMS, grid=GRID,
        bases=BASES, val_seeds=list(SPLITS["val"]), test_seeds=TEST_SEEDS,
        load_metric="flow_mods = installs + deletes + demotes per episode (Packet-Ins reported)",
        selection=f"per base: fewest mean flow_mods over A1-A7 validation episodes among settings "
                  f"with mean benign harm (A1-A7 + benign) <= base + {HARM_MARGIN}; ties within "
                  f"1 % of flow_mods: lower harm; none eligible: no hold",
        test_cells="A1-A7, benign and E9's three selected attacks; dedicated ports",
        comparison="dms-blocklist (revision 2 knobs B) as the load reference",
        hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    if not os.path.exists(path):
        _load()
        cells = [(d, v, s) for d in DOMS for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
        tasks = [("select", n, *c) for n in BASES + _candidates() for c in cells]
        _run(tasks, workers, "select").to_csv(path, index=False)
    df = pd.read_csv(path)
    att = df[df.variant != "benign"]
    harm = df.groupby("defense").benign_flows_harmed_frac.mean()
    load = att.groupby("defense").flow_mods.mean()
    sel, rows = {}, []
    for b in BASES:
        cand = [c for c in _candidates() if c.startswith(b + "|")]
        for c in [b] + cand:
            rows.append(dict(base=b, defense=c, harm_pct=round(100 * harm[c], 3),
                             flow_mods=round(load[c]), eligible=bool(harm[c] <= harm[b] + HARM_MARGIN)))
        ok = [c for c in cand if harm[c] <= harm[b] + HARM_MARGIN]
        if not ok:
            sel[b] = b
            continue
        best = min(load[c] for c in ok)
        near = [c for c in ok if load[c] <= 1.01 * best]
        sel[b] = min(near, key=lambda c: harm[c])
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel))
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps(sel, indent=1))


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    e9 = sorted({b["attack"] for b in json.load(open(os.path.join(E9.OUT, "selected.json"))).values()})
    names = list(dict.fromkeys(BASES + list(sel.values()) + ["dms-blocklist"]))
    cells = [(d, v, s) for d in DOMS for v in list(VARIANTS) + [None] + e9 for s in TEST_SEEDS]
    _run([("test", n, *c) for n in names for c in cells], workers, "test").to_csv(path, index=False)


def _boot_upper(diff, clusters, n=2000, seed=0):
    """95 % upper bound of the mean of diff, resampling clusters."""
    rng = np.random.default_rng(seed)
    keys = np.unique(clusters)
    by = {k: diff[clusters == k] for k in keys}
    means = [np.concatenate([by[k] for k in rng.choice(keys, len(keys))]).mean() for _ in range(n)]
    return float(np.percentile(means, 97.5))


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    std = list(VARIANTS) + ["benign"]
    df["group"] = np.where(df.variant.isin(VARIANTS), "A1-A7",
                           np.where(df.variant == "benign", "benign", "E9"))
    piv = df.groupby(["domain", "group", "defense"])[
        ["benign_flows_harmed_frac", "flow_mods", "packet_in", "installs", "blocked_pkts"]].mean()
    piv["benign_flows_harmed_frac"] *= 100
    piv.round(2).to_csv(os.path.join(tdir, "by_domain_group.csv"))
    t1a2 = df[(df.domain == "T1") & (df.variant == "A2")].groupby("defense")[
        ["benign_flows_harmed_frac", "flow_mods", "installs", "packet_in"]].mean()
    t1a2.to_csv(os.path.join(tdir, "t1_a2.csv"))
    rows, tests = [], []
    for b, s in sel.items():
        if s == b:
            rows.append(dict(base=b, selected=s, note="no hold selected"))
            continue
        att = df[df.variant != "benign"]
        md, w, l, p = R1.cluster_wilcoxon(att, "flow_mods", s, b)
        tests.append(dict(hyp="HH1", a=s, b=b, metric="flow_mods", mean_diff=md, a_lower=w,
                          a_higher=l, p=p))
        red = 1 - t1a2.loc[s, "flow_mods"] / t1a2.loc[b, "flow_mods"]
        h = df[df.variant.isin(std)]
        A = h[h.defense == s].set_index(["domain", "variant", "seed"]).benign_flows_harmed_frac
        B_ = h[h.defense == b].set_index(["domain", "variant", "seed"]).benign_flows_harmed_frac
        d = (A - B_.reindex(A.index)).values
        cl = np.array([f"{i[0]}|{i[1]}" for i in A.index])
        upper = _boot_upper(d, cl)
        md2, w2, l2, p2 = R1.cluster_wilcoxon(h, "benign_flows_harmed_frac", s, b)
        tests.append(dict(hyp="HH2", a=s, b=b, metric="harm", mean_diff=md2, a_lower=w2,
                          a_higher=l2, p=p2))
        e = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()
        worst_s, worst_b = 100 * e.loc[s].max(), 100 * e.loc[b].max()
        rows.append(dict(base=b, selected=s, t1_a2_flowmod_reduction_pct=round(100 * red, 1),
                         HH1_t1a2=bool(red >= 0.30),
                         harm_diff_pct=round(100 * float(d.mean()), 3),
                         harm_diff_upper95_pct=round(100 * upper, 3), HH2=bool(upper <= 0.005),
                         e9_worst_selected=round(worst_s, 2), e9_worst_base=round(worst_b, 2),
                         HH3=bool(worst_s <= worst_b + 0.5)))
    t = pd.DataFrame(tests)
    if len(t):
        t["p_holm"] = holm(t.p.values)
        t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(tdir, "summary.csv"), index=False)
    pd.set_option("display.width", 250)
    print((piv.round(2)).to_string())
    print(t1a2.round(4).to_string())
    print(s.to_string(index=False))
    if len(t):
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
