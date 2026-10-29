"""Revision step 4: survive the adaptive fast-refresh attacker (review item 1).

    python -m loftbench.revision4 --out results/revision4 --stages prereg,select,test,report

Soft demotion only removes flows that refresh more slowly than t_short, and the
v2.1 detector flags about 2 % of fast-refresh entries, so an attacker refreshing
every 0.9 s holds the table under every defense. The added mechanism is
PortGuard (`defenses.PortGuard`): under table pressure each ingress port gets a
max-min fair share of the table, enforced at admission time. Spoofing changes
source addresses, not the access port, so the bound holds for any refresh rate.

Candidates (PortGuard knobs on top of v2.1) are selected on validation seeds
2000-2002 in the DMS-BTT topology (dedicated attacker ports) under a rule fixed
here before any run. The selected knobs are then tested once on fresh seeds
6000-6009 (dedicated) and 6000-6004 (shared and distributed ports, see
`ports.py`), against an attacker-budget sweep of refresh gaps 0.25-9 s.
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

import numpy as np
import pandas as pd

from . import revision2, v21
from .config import DOMAINS, VARIANTS, SimConfig, gap_variant
from .data import DOMAIN_IDX
from .defenses import PortGuard
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .revision1 import cluster_boot, cluster_wilcoxon
from .sim import Defense, run_episode
from .traffic import build_traffic

CFG = SimConfig(duration=300.0)
VAL_SEEDS = list(SPLITS["val"])
TEST_SEEDS = list(range(6000, 6010))
TEST_SEEDS_ALT = TEST_SEEDS[:5]
GAPS = [0.25, 0.5, 0.8, 1.0, 2.0, 5.0, 9.0]


ATTACKS = dict(VARIANTS, **{f"X{g:g}": gap_variant(g) for g in GAPS})
STANDARD = list(VARIANTS)
GAP_KEYS = [f"X{g:g}" for g in GAPS]
FAST_KEYS = [f"X{g:g}" for g in GAPS if g <= 1.0]
DEFENSES = ["none", "dms-blocklist", "v2.1", "pfs", "v2.1+pfs", "dms-blocklist+pfs"]
CANDIDATES = [dict(id=f"q{q}-r{q + dr:.2f}-h{h:g}", q=q, rho_q=round(q + dr, 2), hold_s=h)
              for q, dr, h in itertools.product([0.85, 0.90, 0.95], [0.0, -0.05], [10.0, 30.0])]
RULE = dict(
    data="validation seeds 2000-2002, dedicated ports, D1-D3, A1-A7 + gap sweep + benign-only",
    feasible=("mean benign harm on A1-A7 <= v2.1's + 0.5 points and benign-only harm <= "
              "v2.1's + 0.1 points"),
    objective="minimise mean benign harm over the gap sweep",
    tie_break="within 0.05 points: lower mean attacker occupancy over the gap sweep, then fewer "
              "overflow seconds",
    fallback="if none is feasible: minimise total constraint violation (points), then the objective",
    applies_to="the selected knobs are used for v2.1+pfs, pfs and dms-blocklist+pfs",
)
HYPOTHESES = dict(
    H1="dedicated: over gaps <= 1 s, v2.1+pfs harms fewer benign flows than v2.1 (cluster Wilcoxon, Holm)",
    H2="dedicated: on A1-A7, v2.1+pfs is non-inferior to v2.1 (mean harm difference <= 0.5 points)",
    H3="dedicated: on A1-A7, v2.1+pfs harms fewer than pfs alone (detector contribution)",
    H4="dedicated: over all attacks, v2.1+pfs harms fewer than dms-blocklist+pfs",
    H5="dedicated: at every gap, v2.1+pfs mean harm <= 3 %",
    H6="distributed (expected negative): over gaps <= 1 s, v2.1+pfs does not reduce harm vs v2.1",
)
_CTX = {}


# ---------------------------------------------------------------- defenses
def _load(src, v21dir, rev2):
    sel = json.load(open(os.path.join(v21dir, "selected.json")))["selected"]
    v21._load_ctx(src, v21dir, sel)
    revision2._load(rev2)
    _CTX["dmsB"] = json.load(open(os.path.join(rev2, "selected.json")))["selected"]["B"]


def make(name, d, knobs):
    if name == "none":
        return Defense()
    base, _, pfs = name.partition("+")
    if base == "pfs":
        return PortGuard(None, name=name, **knobs)
    inner = revision2.make(_CTX["dmsB"], d) if base == "dms-blocklist" else v21._make("v2.1", d, None)
    return PortGuard(inner, name=name, **knobs) if pfs else inner


def _episode(args):
    name, knobs, kid, scen, d, v, s = args
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], ATTACKS[v] if v else None, s,
                                    CFG.duration, CFG.attack_start), scen)
    r = run_episode(tr, CFG, make(name, d, knobs), record_ts=False).summary
    span = CFG.duration - CFG.attack_start
    return dict(defense=name, cfg_id=kid, scenario=scen, domain=d, variant=v or "benign", seed=s,
                packet_in_per_s=r["packet_in"] / CFG.duration, attack_pps=r["attack_pkts"] / span,
                **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 300 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


def _knobs(c):
    return dict(q=c["q"], rho_q=c["rho_q"], hold_s=c["hold_s"])


# ---------------------------------------------------------------- prereg
def stage_prereg(out):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(out, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), mechanism="PortGuard on top of v2.1",
        candidates=CANDIDATES, rule=RULE, hypotheses=HYPOTHESES, defenses=DEFENSES,
        gaps_s=GAPS, gap_variant="step 100, t1 in [0.9g, g], benign sizes, spoofed sources, "
                                 "burst rate max(1500, 1.25*1700/(0.9g)) pps per attacker",
        scenarios=dict(main="dedicated", generalisation=["shared", "distributed"]),
        val_seeds=VAL_SEEDS, test_seeds=dict(dedicated=TEST_SEEDS, shared=TEST_SEEDS_ALT,
                                             distributed=TEST_SEEDS_ALT),
        primary_metric="benign_flows_harmed_frac",
        statistics="cluster bootstrap and cluster Wilcoxon over (domain, seed), Holm within family",
        fixed=dict(v21="results/v21 selected configuration",
                   dms_blocklist="results/revision2 family B (tuned DMS-BTT + blocklist)")))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


# ---------------------------------------------------------------- select
def select(df):
    """Apply RULE to validation episodes (one row per episode)."""
    ref = df[df.defense == "v2.1"]
    ref_std = ref[ref.variant.isin(STANDARD)].benign_flows_harmed_frac.mean()
    ref_ben = ref[ref.variant == "benign"].benign_flows_harmed_frac.mean()
    rows = []
    for kid, g in df[df.defense == "v2.1+pfs"].groupby("cfg_id"):
        std = g[g.variant.isin(STANDARD)].benign_flows_harmed_frac.mean()
        ben = g[g.variant == "benign"].benign_flows_harmed_frac.mean()
        gap = g[g.variant.isin(GAP_KEYS)]
        viol = 100 * (max(0.0, std - ref_std - 0.005) + max(0.0, ben - ref_ben - 0.001))
        rows.append(dict(cfg_id=kid, harm_standard=std, harm_benign_only=ben,
                         harm_gaps=gap.benign_flows_harmed_frac.mean(),
                         occ_gaps=gap.avg_attack_occ_post.mean(),
                         overflow_gaps=gap.overflow_seconds_post_attack.mean(), violation=viol))
    t = pd.DataFrame(rows)
    t["feasible"] = t.violation == 0
    pool = t[t.feasible] if t.feasible.any() else t[t.violation == t.violation.min()]
    best = pool.harm_gaps.min()
    pool = pool[pool.harm_gaps <= best + 0.0005].sort_values(["occ_gaps", "overflow_gaps"])
    return t.assign(ref_harm_standard=ref_std, ref_harm_benign_only=ref_ben), pool.iloc[0].cfg_id


def stage_select(out, workers):
    if not os.path.exists(os.path.join(out, "preregistration.json")):
        raise SystemExit("run the prereg stage first")
    variants = STANDARD + GAP_KEYS + [None]
    tasks = [("v2.1", {}, "ref", "dedicated", d, v, s) for d in DOMAINS for v in variants
             for s in VAL_SEEDS]
    tasks += [("v2.1+pfs", _knobs(c), c["id"], "dedicated", d, v, s) for c in CANDIDATES
              for d in DOMAINS for v in variants for s in VAL_SEEDS]
    df = _run(tasks, workers, "select")
    df.to_csv(os.path.join(out, "selection_validation.csv"), index=False)
    t, best = select(df)
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
    tasks = []
    for scen, seeds in (("dedicated", TEST_SEEDS), ("shared", TEST_SEEDS_ALT),
                        ("distributed", TEST_SEEDS_ALT)):
        for n in DEFENSES:
            k = _knobs(c) if "pfs" in n else {}
            tasks += [(n, k, c["id"] if k else "-", scen, d, v, s) for d in DOMAINS
                      for v in variants for s in seeds]
    df = _run(tasks, workers, "test")
    df.to_csv(path, index=False)


# ---------------------------------------------------------------- report
LABEL = {"none": "No defense", "dms-blocklist": "DMS-BTT tuned + blocklist", "v2.1": "FL-DualGuard v2.1",
         "pfs": "PortGuard alone", "v2.1+pfs": "v2.1 + PortGuard",
         "dms-blocklist+pfs": "DMS-BTT tuned + blocklist + PortGuard"}


def _ci(g, m, scale=100):
    mu, lo, hi = cluster_boot(g, m)
    return f"{scale * mu:.2f} [{scale * lo:.2f}, {scale * hi:.2f}]"


def stage_report(out):
    from .report import holm
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    df = pd.read_csv(os.path.join(out, "test_episodes.csv"))
    att = df[df.variant != "benign"]
    groups = dict(standard=STANDARD, fast=FAST_KEYS, gaps=GAP_KEYS)

    # Summary per scenario and attack group.
    rows = []
    for scen, gs in att.groupby("scenario"):
        for grp, keys in groups.items():
            g0 = gs[gs.variant.isin(keys)]
            for n in DEFENSES:
                g = g0[g0.defense == n]
                rows.append({"scenario": scen, "attacks": grp, "method": LABEL[n],
                             "harmed (%)": _ci(g, "benign_flows_harmed_frac"),
                             "mal_occ (%)": round(100 * g.avg_attack_occ_post.mean(), 2),
                             "overflow_s": round(g.overflow_seconds_post_attack.mean(), 2),
                             "packet_in_per_s": round(g.packet_in_per_s.mean(), 1)})
    ben = df[df.variant == "benign"].groupby(["scenario", "defense"]).benign_flows_harmed_frac.mean()
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_summary.csv"), index=False)
    (100 * ben).round(3).unstack().rename(columns=LABEL).to_csv(os.path.join(tdir, "table_benign_only.csv"))

    # Attacker-budget curve (dedicated is the main topology).
    for m, f in (("benign_flows_harmed_frac", "harm"), ("avg_attack_occ_post", "occ")):
        cur = (att[att.variant.isin(GAP_KEYS)]
               .pivot_table(index=["scenario", "variant"], columns="defense", values=m) * 100).round(2)
        cur = cur.reindex(columns=DEFENSES).rename(columns=LABEL)
        cur.to_csv(os.path.join(tdir, f"table_budget_curve_{f}.csv"))
    cost = att[att.variant.isin(GAP_KEYS) & (att.defense == "none")].groupby("variant").attack_pps.mean()
    cost.round(0).to_csv(os.path.join(tdir, "table_attacker_pps.csv"))
    (att[att.scenario == "dedicated"].pivot_table(index="variant", columns="defense",
                                                  values="benign_flows_harmed_frac") * 100) \
        .round(2).reindex(columns=DEFENSES).rename(columns=LABEL) \
        .to_csv(os.path.join(tdir, "table_dedicated_by_variant.csv"))

    # Pre-registered tests.
    ded, dist = att[att.scenario == "dedicated"], att[att.scenario == "distributed"]
    M = "benign_flows_harmed_frac"
    spec = [("H1", ded[ded.variant.isin(FAST_KEYS)], "v2.1+pfs", "v2.1"),
            ("H2", ded[ded.variant.isin(STANDARD)], "v2.1+pfs", "v2.1"),
            ("H3", ded[ded.variant.isin(STANDARD)], "v2.1+pfs", "pfs"),
            ("H4", ded, "v2.1+pfs", "dms-blocklist+pfs"),
            ("H6", dist[dist.variant.isin(FAST_KEYS)], "v2.1+pfs", "v2.1")]
    tests = []
    for h, g, a, b in spec:
        md, w, l, p = cluster_wilcoxon(g, M, a, b)
        tests.append(dict(hypothesis=h, a=LABEL[a], b=LABEL[b], mean_cluster_diff_points=100 * md,
                          a_wins=w, a_losses=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    t.to_csv(os.path.join(tdir, "hypothesis_tests.csv"), index=False)
    per_gap = ded[ded.defense == "v2.1+pfs"].groupby("variant")[M].mean().reindex(GAP_KEYS) * 100
    outcome = dict(
        H1=bool(t.loc[0, "p_holm"] < 0.05 and t.loc[0, "mean_cluster_diff_points"] < 0),
        H2=bool(t.loc[1, "mean_cluster_diff_points"] <= 0.5),
        H3=bool(t.loc[2, "p_holm"] < 0.05 and t.loc[2, "mean_cluster_diff_points"] < 0),
        H4=bool(t.loc[3, "p_holm"] < 0.05 and t.loc[3, "mean_cluster_diff_points"] < 0),
        H5=bool((per_gap <= 3.0).all()), H5_per_gap_harm=per_gap.round(3).to_dict(),
        H6_no_reduction=bool(not (t.loc[4, "p_holm"] < 0.05 and t.loc[4, "mean_cluster_diff_points"] < 0)))
    _dump(out, "outcomes.json", outcome)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in sorted(os.listdir(tdir)):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))
    print(json.dumps(outcome, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--v21", default="results/v21")
    ap.add_argument("--rev2", default="results/revision2")
    ap.add_argument("--out", default="results/revision4")
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
