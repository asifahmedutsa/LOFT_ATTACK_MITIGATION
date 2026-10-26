"""Revision step 1: service-level harm, tail statistics, cluster-bootstrap CIs and
per-flow calibration, measured on the existing v2.1 configuration.

    python -m loftbench.revision1 --src results/v2 --v21 results/v21 --out results/revision1

Stages (default all):
  flowcal    per-flow threshold on validation runs (no defense, val seeds)
  valcheck   v2.1 vs v2.1 with per-flow threshold, validation seeds only
  remeasure  rerun the v2.1 test defenses on seeds 5000-5009 with the new harm
             metrics; checks the original metrics reproduce exactly
  report     tables

No configuration is selected here and the fresh test seeds are only re-measured
with the already-tested configuration; the per-flow variant is evaluated on
validation seeds only, so seeds 6000+ stay untouched for the next confirmatory
test.
"""
import os

# One BLAS thread per worker process (see experiment.py).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import v21
from .config import DOMAINS, EXPOSURE, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DualGuard
from .experiment import BUDGET, COLLECT_CFG, SPLITS, _dump
from .sim import Defense, run_episode
from .traffic import build_traffic

ONLINE_CFG = SimConfig(duration=300.0)
NEW_METRICS = ["benign_flows_harmed_frac", "benign_flows_active_evicted_frac",
               "benign_flows_stale_evicted_frac", "benign_evict_repackets"]
FLOWCAL = {}


def _detector(d):
    models, taus, _, sel = v21._CTX
    return models[sel["detector"]], taus[f"{sel['detector']}/{d}"]


class _MaxScore:
    """collect() hook: running max detector score per flow while installed."""

    def __init__(self, model, n_flows):
        self.model = model
        self.mx = np.full(n_flows, -1.0)

    def __call__(self, t, fids, obs, lab):
        if len(fids):
            s = self.model.predict_proba(obs["X"])
            np.maximum.at(self.mx, fids, s)


# ---------------------------------------------------------------- flowcal
def _flowcal_task(args):
    d, v, s = args
    model, tau_poll = _detector(d)
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       COLLECT_CFG.duration, COLLECT_CFG.attack_start)
    hook = _MaxScore(model, tr.n_flows)
    run_episode(tr, COLLECT_CFG, Defense(), collect=hook, record_ts=False)
    ben = (~tr.flow_attack) & (hook.mx >= 0)
    return d, hook.mx[ben]


def stage_flowcal(out, workers):
    tasks = [(d, v, s) for d in DOMAINS for v in list(EXPOSURE[d]) + [None] for s in SPLITS["val"]]
    with get_context("fork").Pool(workers) as p:
        res = p.map(_flowcal_task, tasks)
    rows = {}
    for d in DOMAINS:
        mx = np.concatenate([m for dd, m in res if dd == d])
        _, tau_poll = _detector(d)
        tau_flow = float(np.quantile(mx, 1 - BUDGET)) + 1e-9
        rows[d] = dict(n_benign_flows=int(len(mx)), tau_poll=tau_poll, tau_flow=tau_flow,
                       val_flow_flag_rate_at_tau_poll=float((mx >= tau_poll).mean()),
                       val_flow_flag_rate_at_tau_flow=float((mx >= tau_flow).mean()))
    _dump(out, "flowcal.json", dict(budget=BUDGET, detector=v21._CTX[3]["detector"],
                                    definition="tau_flow = (1-budget) quantile of each benign "
                                               "flow's max score over all polls while installed, "
                                               "validation runs without defense", domains=rows))
    print(pd.DataFrame(rows).T.round(4))


def _load_flowcal(out):
    FLOWCAL.update(json.load(open(os.path.join(out, "flowcal.json")))["domains"])


# ---------------------------------------------------------------- episodes
def _make(name, d):
    if name == "v2.1-flowcal":
        model, _ = _detector(d)
        return DualGuard(model, FLOWCAL[d]["tau_flow"], **v21._policy(v21._CTX[3]))
    return v21._make(name, d, None)


def _episode(args):
    name, d, v, s = args
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       ONLINE_CFG.duration, ONLINE_CFG.attack_start)
    hook = None
    if name in ("v2.1", "v2.1-flowcal"):
        model, _ = _detector(d)
        hook = _MaxScore(model, tr.n_flows)
    r = run_episode(tr, ONLINE_CFG, _make(name, d), collect=hook, record_ts=False).summary
    row = dict(defense=name, domain=d, variant=v or "benign", seed=s, **r)
    if hook is not None:
        ben = (~tr.flow_attack) & (hook.mx >= 0)
        mx = hook.mx[ben]
        row.update(flow_flag_rate_tau_poll=float((mx >= v21._CTX[1][f"{v21._CTX[3]['detector']}/{d}"]).mean()),
                   flow_flag_rate_tau_flow=float((mx >= FLOWCAL[d]["tau_flow"]).mean()))
    return row


def _run(tasks, workers, tag):
    rows = []
    t0 = time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


def stage_valcheck(out, workers):
    tasks = [(n, d, v, s) for n in ("v2.1", "v2.1-flowcal") for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
    _run(tasks, workers, "valcheck").to_csv(os.path.join(out, "valcheck_episodes.csv"), index=False)


def stage_remeasure(v21_dir, out, workers):
    tasks = [(n, d, v, s) for n in v21.TEST_DEFENSES for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in v21.FRESH_SEEDS]
    df = _run(tasks, workers, "remeasure")
    df.to_csv(os.path.join(out, "remeasure_episodes.csv"), index=False)
    orig = pd.read_csv(os.path.join(v21_dir, "test_episodes.csv"))
    key = ["defense", "domain", "variant", "seed"]
    j = orig.merge(df, on=key, suffixes=("_orig", "_new"))
    cols = [c for c in orig.columns if c not in key and not c.startswith("decision_ms")
            and c != "first_overflow_s"]
    bad = [c for c in cols if not np.allclose(j[c + "_orig"], j[c + "_new"], equal_nan=True)]
    fo = np.allclose(j.first_overflow_s_orig.fillna(-1), j.first_overflow_s_new.fillna(-1))
    _dump(out, "determinism_check.json", dict(pairs=len(j), expected=len(orig),
                                              mismatched_columns=bad + ([] if fo else ["first_overflow_s"]),
                                              ok=len(j) == len(orig) and not bad and fo))
    print("determinism:", "OK" if (len(j) == len(orig) and not bad and fo) else f"MISMATCH {bad}")


# ---------------------------------------------------------------- statistics
def cluster_boot(df, metric, clusters=("domain", "seed"), n=4000, seed=0):
    """Mean and 95% percentile CI resampling whole (domain, seed) clusters."""
    g = df.groupby(list(clusters))[metric].agg(["sum", "count"])
    s, c = g["sum"].values, g["count"].values
    r = np.random.default_rng(seed)
    idx = r.integers(0, len(s), (n, len(s)))
    means = s[idx].sum(1) / c[idx].sum(1)
    return s.sum() / c.sum(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def cluster_wilcoxon(df, metric, a, b):
    from scipy.stats import wilcoxon
    m = df.groupby(["defense", "domain", "seed"])[metric].mean().unstack(0)
    d = m[a] - m[b]
    p = 1.0 if (d == 0).all() else wilcoxon(m[a], m[b], zero_method="zsplit").pvalue
    return float(d.mean()), int((d < 0).sum()), int((d > 0).sum()), float(p)


def _fmt(df, metric, scale=100):
    mu, lo, hi = cluster_boot(df, metric)
    return f"{mu * scale:.2f} [{lo * scale:.2f}, {hi * scale:.2f}]"


def stage_report(out):
    from .report import LABEL, holm
    LABEL = dict(LABEL, **{"v2": "FL-DualGuard v2", "v2.1": "FL-DualGuard v2.1",
                           "dg-local-noctx": "Local MLP (no ctx) + v2.1 policy",
                           "v2.1-flowcal": "v2.1, per-flow calibrated"})
    df = pd.read_csv(os.path.join(out, "remeasure_episodes.csv"))
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    # Extra benign Packet-Ins relative to the same benign traffic with no attack and
    # no defense (paired on domain, seed).
    base = df[(df.defense == "none") & (df.variant == "benign")].set_index(["domain", "seed"])
    df["extra_benign_packet_in_per_1k"] = [
        1000 * (r.benign_packet_in - base.loc[(r.domain, r.seed), "benign_packet_in"]) / r.benign_pkts
        for r in df.itertuples()]
    att = df[df.variant != "benign"]
    order = [d for d in v21.TEST_DEFENSES]

    harm = []
    for d in order:
        g = att[att.defense == d]
        harm.append({
            "defense": LABEL.get(d, d),
            "Harmed: rejected or evicted while active (%)": _fmt(g, "benign_flows_harmed_frac"),
            "Refused an entry (%)": _fmt(g, "benign_flows_rejected_frac"),
            "Evicted while active (%)": _fmt(g, "benign_flows_active_evicted_frac"),
            "Stale entries removed (%) [no harm]": _fmt(g, "benign_flows_stale_evicted_frac"),
            "Old metric: impacted (%)": _fmt(g, "benign_flows_impacted_frac"),
            "Extra benign Packet-In per 1k benign pkts": _fmt(g, "extra_benign_packet_in_per_1k", 1),
            "Malicious occupancy (%)": _fmt(g, "avg_attack_occ_post"),
        })
    pd.DataFrame(harm).to_csv(os.path.join(tdir, "table_harm_attack.csv"), index=False)

    tails = []
    for d in order:
        o = att[att.defense == d].overflow_seconds_post_attack
        mu, lo, hi = cluster_boot(att[att.defense == d], "overflow_seconds_post_attack")
        tails.append(dict(defense=LABEL.get(d, d), mean=f"{mu:.2f} [{lo:.2f}, {hi:.2f}]",
                          median=round(o.median(), 2), p90=round(o.quantile(0.9), 2),
                          p99=round(o.quantile(0.99), 2), max=round(o.max(), 2),
                          share_gt_5s=round((o > 5).mean(), 3), share_gt_10s=round((o > 10).mean(), 3)))
    pd.DataFrame(tails).to_csv(os.path.join(tdir, "table_overflow_tails.csv"), index=False)

    pv = att[att.defense == "v2.1"]
    per_var = pv.groupby("variant").agg(
        harmed_pct=("benign_flows_harmed_frac", lambda x: 100 * x.mean()),
        impacted_pct_old=("benign_flows_impacted_frac", lambda x: 100 * x.mean()),
        mal_occ_pct=("avg_attack_occ_post", lambda x: 100 * x.mean()),
        overflow_mean=("overflow_seconds_post_attack", "mean"),
        overflow_p90=("overflow_seconds_post_attack", lambda x: x.quantile(0.9)),
        share_gt_5s=("overflow_seconds_post_attack", lambda x: (x > 5).mean())).round(2)
    per_var.to_csv(os.path.join(tdir, "table_v21_by_variant.csv"))

    dom = []
    for d in order:
        row = {"defense": LABEL.get(d, d)}
        for dm in DOMAINS:
            g = att[(att.defense == d) & (att.domain == dm)]
            mu, lo, hi = cluster_boot(g, "benign_flows_harmed_frac")
            row[f"{dm} harmed (%)"] = f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]"
        dom.append(row)
    pd.DataFrame(dom).to_csv(os.path.join(tdir, "table_harm_by_domain.csv"), index=False)

    tests = []
    for m in ("benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"):
        for b in order:
            if b == "v2.1":
                continue
            md, w, l, p = cluster_wilcoxon(att, m, "v2.1", b)
            tests.append(dict(metric=m, baseline=LABEL.get(b, b), clusters=30,
                              mean_cluster_diff=md, cluster_wins=w, cluster_losses=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = np.concatenate([holm(g.p.values) for _, g in t.groupby("metric", sort=False)])
    t.to_csv(os.path.join(tdir, "cluster_paired_tests.csv"), index=False)

    # Per-flow calibration.
    fc = json.load(open(os.path.join(out, "flowcal.json")))
    v = df[df.defense == "v2.1"]
    cal = []
    for dm in DOMAINS:
        g = v[v.domain == dm]
        f = fc["domains"][dm]
        cal.append(dict(domain=dm, tau_poll=round(f["tau_poll"], 4), tau_flow=round(f["tau_flow"], 4),
                        val_flow_rate_tau_poll=round(f["val_flow_flag_rate_at_tau_poll"], 4),
                        val_flow_rate_tau_flow=round(f["val_flow_flag_rate_at_tau_flow"], 4),
                        test_flow_rate_tau_poll_attacked=round(g[g.variant != "benign"].flow_flag_rate_tau_poll.mean(), 4),
                        test_flow_rate_tau_poll_benign_only=round(g[g.variant == "benign"].flow_flag_rate_tau_poll.mean(), 4),
                        test_flow_rate_tau_flow_attacked=round(g[g.variant != "benign"].flow_flag_rate_tau_flow.mean(), 4),
                        test_flow_rate_tau_flow_benign_only=round(g[g.variant == "benign"].flow_flag_rate_tau_flow.mean(), 4),
                        test_acted_on_rate_benign_only=round(g[g.variant == "benign"].benign_flows_evicted_frac.mean(), 4)))
    pd.DataFrame(cal).to_csv(os.path.join(tdir, "table_flow_calibration.csv"), index=False)

    vc_path = os.path.join(out, "valcheck_episodes.csv")
    if os.path.exists(vc_path):
        vc = pd.read_csv(vc_path)
        rows = []
        for d in ("v2.1", "v2.1-flowcal"):
            for scope, g in (("attacked", vc[(vc.defense == d) & (vc.variant != "benign")]),
                             ("benign-only", vc[(vc.defense == d) & (vc.variant == "benign")])):
                rows.append(dict(defense=LABEL[d], scope=scope, episodes=len(g),
                                 harmed=_fmt(g, "benign_flows_harmed_frac"),
                                 acted_on=_fmt(g, "benign_flows_evicted_frac"),
                                 mal_occ=_fmt(g, "avg_attack_occ_post"),
                                 overflow_mean=round(g.overflow_seconds_post_attack.mean(), 2),
                                 overflow_p90=round(g.overflow_seconds_post_attack.quantile(0.9), 2),
                                 flow_flag_rate=round(g.flow_flag_rate_tau_flow.mean() if d.endswith("flowcal")
                                                      else g.flow_flag_rate_tau_poll.mean(), 4)))
        pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_flowcal_validation.csv"), index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in sorted(os.listdir(tdir)):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--v21", default="results/v21")
    ap.add_argument("--out", default="results/revision1")
    ap.add_argument("--stages", default="flowcal,valcheck,remeasure,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sel = json.load(open(os.path.join(a.v21, "selected.json")))["selected"]
    v21._load_ctx(a.src, a.v21, sel)
    st = a.stages.split(",")
    if "flowcal" in st:
        stage_flowcal(a.out, a.workers)
    if {"valcheck", "remeasure", "report"} & set(st):
        _load_flowcal(a.out)
    if "valcheck" in st:
        stage_valcheck(a.out, a.workers)
    if "remeasure" in st:
        stage_remeasure(a.v21, a.out, a.workers)
    if "report" in st:
        stage_report(a.out)


if __name__ == "__main__":
    main()
