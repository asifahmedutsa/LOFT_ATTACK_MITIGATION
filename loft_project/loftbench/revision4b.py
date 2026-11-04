"""Revision step 4b: make DualGuard and PortGuard cooperate (review item 1, continued).

    python -m loftbench.revision4b --out results/revision4b --stages prereg,select,test,report

Step 4 (results_v2.md §14) found that running DualGuard on the whole table while
PortGuard holds it near full makes DualGuard demote many benign entries, whose
slots water-filling then hands to attacker ports. Step 4b pre-registers two
non-conflicting compositions (`PortGuard.mode`):

  gated   DualGuard pauses while PortGuard is enforcing
  scoped  while PortGuard is enforcing, DualGuard only sees entries of ports
          above their fair level

and two share rules (`PortGuard.share`): equal max-min shares (step 4), or
weighted max-min shares, each port weighted by its entry count averaged over polls
without table pressure (calm-period demand fits in the table by construction).

Selection on validation seeds 2000-2002 uses the step-4 rule unchanged. The test
runs once on fresh seeds 8000-8009 (dedicated ports) and 8000-8004 (shared,
distributed). The traffic, attacks, v2.1 and DMS-BTT models are those of step 4.
"""
import os

# One BLAS thread per worker process (see experiment.py).
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

from . import revision2, revision4, v21
from .config import DOMAINS
from .data import DOMAIN_IDX
from .defenses import PortGuard
from .experiment import _dump
from .ports import assign_ports
from .revision1 import cluster_boot, cluster_wilcoxon
from .revision4 import (ATTACKS, CFG, FAST_KEYS, GAP_KEYS, GAPS, STANDARD, VAL_SEEDS, _CTX,
                        _load)
from .sim import Defense, run_episode
from .traffic import build_traffic

TEST_SEEDS = list(range(8000, 8010))
TEST_SEEDS_ALT = TEST_SEEDS[:5]
STEP4 = dict(q=0.95, rho_q=0.90, hold_s=30.0)     # step-4 selection (results/revision4)
CANDIDATES = [dict(id=f"{m}-{s}-q{q}", mode=m, share=s, q=q, rho_q=0.90, hold_s=30.0, tau_s=60.0)
              for m, s, q in itertools.product(["gated", "scoped"], ["equal", "weighted"],
                                               [0.90, 0.95])]
RULE = dict(revision4.RULE, applies_to="the selected candidate is v2.1+pfs4b; pfs-sel is "
                                       "PortGuard alone with the selected share and q")
DEFENSES = ["none", "dms-blocklist", "v2.1", "pfs", "pfs-sel", "v2.1+pfs", "v2.1+pfs4b"]
HYPOTHESES = dict(
    H1="dedicated, gaps <= 1 s: v2.1+pfs4b harms fewer benign flows than the step-4 composition v2.1+pfs",
    H2="dedicated, A1-A7: v2.1+pfs4b is non-inferior to v2.1 (mean harm difference <= 0.5 points)",
    H3="dedicated: v2.1+pfs4b mean harm <= 3 % at every refresh gap",
    H4="dedicated, A1-A7: v2.1+pfs4b harms fewer than PortGuard alone with the same share and q (pfs-sel)",
    H5="shared, gaps <= 1 s: v2.1+pfs4b harms fewer than v2.1",
    H6="distributed, A1-A7: v2.1+pfs4b is non-inferior to v2.1 (<= 0.5 points)",
    H7="distributed, gaps <= 1 s (expected negative): v2.1+pfs4b does not reduce harm vs v2.1",
)


def _pg(c):
    return {k: c[k] for k in ("mode", "share", "q", "rho_q", "hold_s", "tau_s") if k in c}


def make(name, d, cand):
    if name == "none":
        return Defense()
    if name == "dms-blocklist":
        return revision2.make(_CTX["dmsB"], d)
    if name == "v2.1":
        return v21._make("v2.1", d, None)
    if name == "pfs":
        return PortGuard(None, name=name, **STEP4)
    if name == "pfs-sel":
        k = _pg(cand)
        k.pop("mode")
        return PortGuard(None, name=name, **k)
    if name == "v2.1+pfs":
        return PortGuard(v21._make("v2.1", d, None), name=name, **STEP4)
    if name == "v2.1+pfs4b":
        return PortGuard(v21._make("v2.1", d, None), name=name, **_pg(cand))
    raise ValueError(name)


def _episode(args):
    name, cand, scen, d, v, s = args
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], ATTACKS[v] if v else None, s,
                                    CFG.duration, CFG.attack_start), scen)
    r = run_episode(tr, CFG, make(name, d, cand), record_ts=False).summary
    span = CFG.duration - CFG.attack_start
    return dict(defense=name, cfg_id=cand.get("id", "-"), scenario=scen, domain=d,
                variant=v or "benign", seed=s, packet_in_per_s=r["packet_in"] / CFG.duration,
                attack_pps=r["attack_pkts"] / span, **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 300 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- prereg
def stage_prereg(out):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(out, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        motivation="results_v2.md section 14.4: DualGuard and PortGuard conflict under sustained pressure",
        candidates=CANDIDATES, rule=RULE, hypotheses=HYPOTHESES, defenses=DEFENSES,
        step4_knobs=STEP4, gaps_s=GAPS, val_seeds=VAL_SEEDS,
        test_seeds=dict(dedicated=TEST_SEEDS, shared=TEST_SEEDS_ALT, distributed=TEST_SEEDS_ALT),
        development_note="modes and weighted shares were developed on training seed 1000 only",
        primary_metric="benign_flows_harmed_frac",
        statistics="cluster bootstrap and cluster Wilcoxon over (domain, seed), Holm across H1-H7 tests"))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


# ---------------------------------------------------------------- select
def stage_select(out, workers):
    if not os.path.exists(os.path.join(out, "preregistration.json")):
        raise SystemExit("run the prereg stage first")
    variants = STANDARD + GAP_KEYS + [None]
    tasks = [("v2.1", {"id": "ref"}, "dedicated", d, v, s) for d in DOMAINS for v in variants
             for s in VAL_SEEDS]
    tasks += [("v2.1+pfs4b", c, "dedicated", d, v, s) for c in CANDIDATES for d in DOMAINS
              for v in variants for s in VAL_SEEDS]
    df = _run(tasks, workers, "select")
    df.to_csv(os.path.join(out, "selection_validation.csv"), index=False)
    t, best = revision4.select(df.assign(defense=df.defense.replace({"v2.1+pfs4b": "v2.1+pfs"})))
    t.to_csv(os.path.join(out, "selection_table.csv"), index=False)
    c = next(c for c in CANDIDATES if c["id"] == best)
    _dump(out, "selected.json", dict(selected=c, rule=RULE))
    print(t.round(4).to_string(index=False))
    print("selected", best)


# ---------------------------------------------------------------- test
def stage_test(out, workers):
    path = os.path.join(out, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run once; refusing to rerun")
    c = json.load(open(os.path.join(out, "selected.json")))["selected"]
    variants = STANDARD + GAP_KEYS + [None]
    tasks = [(n, c, scen, d, v, s)
             for scen, seeds in (("dedicated", TEST_SEEDS), ("shared", TEST_SEEDS_ALT),
                                 ("distributed", TEST_SEEDS_ALT))
             for n in DEFENSES for d in DOMAINS for v in variants for s in seeds]
    _run(tasks, workers, "test").to_csv(path, index=False)


# ---------------------------------------------------------------- report
LABEL = {"none": "No defense", "dms-blocklist": "DMS-BTT tuned + blocklist",
         "v2.1": "FL-DualGuard v2.1", "pfs": "PortGuard alone (step 4)",
         "pfs-sel": "PortGuard alone (selected share, q)", "v2.1+pfs": "v2.1 + PortGuard (step 4)",
         "v2.1+pfs4b": "v2.1 + PortGuard (step 4b)"}


def stage_report(out):
    from .report import holm
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    df = pd.read_csv(os.path.join(out, "test_episodes.csv"))
    att = df[df.variant != "benign"]
    groups = dict(standard=STANDARD, fast=FAST_KEYS, gaps=GAP_KEYS)
    rows = []
    for scen, gs in att.groupby("scenario"):
        for grp, keys in groups.items():
            g0 = gs[gs.variant.isin(keys)]
            for n in DEFENSES:
                g = g0[g0.defense == n]
                mu, lo, hi = cluster_boot(g, "benign_flows_harmed_frac")
                rows.append({"scenario": scen, "attacks": grp, "method": LABEL[n],
                             "harmed (%)": f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]",
                             "mal_occ (%)": round(100 * g.avg_attack_occ_post.mean(), 2),
                             "overflow_s": round(g.overflow_seconds_post_attack.mean(), 2),
                             "packet_in_per_s": round(g.packet_in_per_s.mean(), 1)})
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_summary.csv"), index=False)
    ben = df[df.variant == "benign"].groupby(["scenario", "defense"]).benign_flows_harmed_frac.mean()
    (100 * ben).round(3).unstack().rename(columns=LABEL).to_csv(os.path.join(tdir, "table_benign_only.csv"))
    for m, f in (("benign_flows_harmed_frac", "harm"), ("avg_attack_occ_post", "occ")):
        cur = (att[att.variant.isin(GAP_KEYS)]
               .pivot_table(index=["scenario", "variant"], columns="defense", values=m) * 100).round(2)
        cur.reindex(columns=DEFENSES).rename(columns=LABEL).to_csv(
            os.path.join(tdir, f"table_budget_curve_{f}.csv"))
    for scen in ("dedicated", "shared", "distributed"):
        (att[att.scenario == scen].pivot_table(index=["variant", "domain"], columns="defense",
                                               values="benign_flows_harmed_frac") * 100) \
            .round(2).reindex(columns=DEFENSES).rename(columns=LABEL) \
            .to_csv(os.path.join(tdir, f"table_{scen}_by_variant_domain.csv"))

    ded = att[att.scenario == "dedicated"]
    sh = att[att.scenario == "shared"]
    dist = att[att.scenario == "distributed"]
    M = "benign_flows_harmed_frac"
    spec = [("H1", ded[ded.variant.isin(FAST_KEYS)], "v2.1+pfs4b", "v2.1+pfs"),
            ("H2", ded[ded.variant.isin(STANDARD)], "v2.1+pfs4b", "v2.1"),
            ("H4", ded[ded.variant.isin(STANDARD)], "v2.1+pfs4b", "pfs-sel"),
            ("H5", sh[sh.variant.isin(FAST_KEYS)], "v2.1+pfs4b", "v2.1"),
            ("H6", dist[dist.variant.isin(STANDARD)], "v2.1+pfs4b", "v2.1"),
            ("H7", dist[dist.variant.isin(FAST_KEYS)], "v2.1+pfs4b", "v2.1")]
    tests = []
    for h, g, a, b in spec:
        md, w, l, p = cluster_wilcoxon(g, M, a, b)
        tests.append(dict(hypothesis=h, a=LABEL[a], b=LABEL[b], mean_cluster_diff_points=100 * md,
                          a_wins=w, a_losses=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    t.to_csv(os.path.join(tdir, "hypothesis_tests.csv"), index=False)
    r = t.set_index("hypothesis")
    per_gap = ded[ded.defense == "v2.1+pfs4b"].groupby("variant")[M].mean().reindex(GAP_KEYS) * 100

    def better(h):
        return bool(r.loc[h, "p_holm"] < 0.05 and r.loc[h, "mean_cluster_diff_points"] < 0)
    outcome = dict(H1=better("H1"), H2=bool(r.loc["H2", "mean_cluster_diff_points"] <= 0.5),
                   H3=bool((per_gap <= 3.0).all()), H3_per_gap_harm=per_gap.round(3).to_dict(),
                   H4=better("H4"), H5=better("H5"),
                   H6=bool(r.loc["H6", "mean_cluster_diff_points"] <= 0.5),
                   H7_no_reduction=not better("H7"))
    _dump(out, "outcomes.json", outcome)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in ("hypothesis_tests.csv", "table_summary.csv", "table_budget_curve_harm.csv",
              "table_benign_only.csv"):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))
    print(json.dumps(outcome, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--v21", default="results/v21")
    ap.add_argument("--rev2", default="results/revision2")
    ap.add_argument("--out", default="results/revision4b")
    ap.add_argument("--stages", default="prereg,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    st = a.stages.split(",")
    if "prereg" in st:
        stage_prereg(a.out)
    if "select" in st or "test" in st:
        _load(a.src, a.v21, a.rev2)
    if "select" in st:
        stage_select(a.out, a.workers)
    if "test" in st:
        stage_test(a.out, a.workers)
    if "report" in st:
        stage_report(a.out)


if __name__ == "__main__":
    main()
