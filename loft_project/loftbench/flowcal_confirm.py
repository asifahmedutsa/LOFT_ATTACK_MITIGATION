"""Confirmatory test: v2.1 with its per-poll threshold vs the per-flow threshold.

The per-flow threshold (tau_flow, results/revision1/flowcal.json) was fixed on validation
seeds in revision 1 and is not changed here. Both thresholds run on seeds 10000-10009, which
no earlier stage has used, with the same detector, policy, domains and attacks.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.flowcal_confirm [--workers 4]

Writes results/flowcal_confirm/{episodes.csv, summary.csv, paired_tests.csv}; refuses to
overwrite an existing episodes.csv (one-shot test).
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json

import pandas as pd

from . import revision1 as R1
from . import v21
from .config import DOMAINS, VARIANTS

SEEDS = list(range(10000, 10010))
DEFENSES = ["v2.1", "v2.1-flowcal"]
OUT = "results/flowcal_confirm"
METRICS = ["benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"]


def report(df):
    att = df[df.variant != "benign"]
    rows = []
    for d in DEFENSES:
        for scope, g in (("attacked", att[att.defense == d]),
                         ("benign-only", df[(df.defense == d) & (df.variant == "benign")])):
            o = g.overflow_seconds_post_attack
            rows.append(dict(defense=d, scope=scope, episodes=len(g),
                             harmed=R1._fmt(g, "benign_flows_harmed_frac"),
                             active_evicted=R1._fmt(g, "benign_flows_active_evicted_frac"),
                             mal_occ=R1._fmt(g, "avg_attack_occ_post"),
                             overflow_mean=round(o.mean(), 2), overflow_p90=round(o.quantile(.9), 2),
                             share_gt_5s=round((o > 5).mean(), 3),
                             flow_flag_rate=round(g.flow_flag_rate_tau_flow.mean() if d.endswith("flowcal")
                                                  else g.flow_flag_rate_tau_poll.mean(), 4)))
    s = pd.DataFrame(rows)
    by = (att.pivot_table(index=["domain"], columns="defense", values=METRICS)
          .round(4))
    tests = []
    for m in METRICS:
        md, w, l, p = R1.cluster_wilcoxon(att, m, "v2.1-flowcal", "v2.1")
        tests.append(dict(metric=m, mean_cluster_diff_flowcal_minus_poll=md, flowcal_lower=w,
                          flowcal_higher=l, p=p))
    return s, by, pd.DataFrame(tests)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "episodes.csv")
    if os.path.exists(path):
        df = pd.read_csv(path)
        print("episodes exist; reporting only")
    else:
        sel = json.load(open("results/v21/selected.json"))["selected"]
        v21._load_ctx("results/v2", "results/v21", sel)
        R1._load_flowcal("results/revision1")
        tasks = [(n, d, v, s) for n in DEFENSES for d in DOMAINS
                 for v in list(VARIANTS) + [None] for s in SEEDS]
        df = R1._run(tasks, a.workers, "confirm")
        df.to_csv(path, index=False)
    s, by, t = report(df)
    s.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    by.to_csv(os.path.join(OUT, "by_domain.csv"))
    t.to_csv(os.path.join(OUT, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 220)
    print(s.to_string(index=False))
    print(by.to_string())
    print(t.round(5).to_string(index=False))


if __name__ == "__main__":
    main()
