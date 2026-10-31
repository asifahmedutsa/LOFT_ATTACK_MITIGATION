"""DualGuard with a Random Forest detector, on the full v2.1 test protocol.

Same policy (results/v21/selected.json), same threshold rule (1 % of benign validation rows
per controller), same domains D1-D3 and attacks A1-A7 plus benign, 300 s episodes, on
seeds 12000-12009 (unused). The RF is trained local, federated and pooled on the v2 datasets.
Trees cannot be weight-averaged, so "federated" shares the three local forests and averages
their probabilities (equivalent to one forest holding all clients' trees). The deployed
FedAvg MLP (v2.1) runs on the same seeds as the reference.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.rf_dualguard [--workers 4]

Writes results/rf_dualguard/{episodes.csv, summary.csv, by_variant.csv, paired_tests.csv}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import revision1 as R1
from . import v21
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DualGuard
from .ml_compare import Mean
from .models import SkWrap, threshold_at_fpr
from .sim import run_episode
from .traffic import build_traffic

SEEDS = list(range(12000, 12010))
DEFENSES = ["v2.1", "rf-local", "rf-federated", "rf-pooled"]
OUT = "results/rf_dualguard"
METRICS = ["benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"]
_M = {}


def _rf(X, y, seed=0):
    from sklearn.ensemble import RandomForestClassifier
    m = RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=seed).fit(X, y)
    m.n_jobs = 1                                 # one core per worker at serving time
    return SkWrap(m)


def train():
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tr = {d: data[("train", d)] for d in DOMAINS}
    local = {d: _rf(tr[d].X, tr[d].y) for d in DOMAINS}
    pooled = _rf(np.concatenate([tr[d].X for d in DOMAINS]), np.concatenate([tr[d].y for d in DOMAINS]))
    fed = Mean(list(local.values()))
    models, taus = {}, {}
    for d in DOMAINS:
        v = data[("val", d)]
        ben = v.X[v.y == 0]
        for how, m in (("local", local[d]), ("federated", fed), ("pooled", pooled)):
            models[(how, d)] = m
            taus[(how, d)] = threshold_at_fpr(m.predict_proba(ben), v21.BUDGET)
    return models, taus


def _episode(args):
    name, d, v, s = args
    cfg = SimConfig(duration=300.0)
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       cfg.duration, cfg.attack_start)
    if name == "v2.1":
        dfn = v21._make("v2.1", d, None)
    else:
        how = name.split("-")[1]
        dfn = DualGuard(_M["models"][(how, d)], _M["taus"][(how, d)], **_M["pol"])
    r = run_episode(tr, cfg, dfn, record_ts=False).summary
    return dict(defense=name, domain=d, variant=v or "benign", seed=s, **r)


def report(df):
    att = df[df.variant != "benign"]
    rows = []
    for d in DEFENSES:
        g = att[att.defense == d]
        b = df[(df.defense == d) & (df.variant == "benign")]
        o = g.overflow_seconds_post_attack
        rows.append(dict(defense=d, harmed=R1._fmt(g, "benign_flows_harmed_frac"),
                         harmed_benign_only=R1._fmt(b, "benign_flows_harmed_frac"),
                         mal_occ=R1._fmt(g, "avg_attack_occ_post"),
                         max_attack_occ=round(100 * g.max_attack_occ.mean(), 2),
                         overflow_mean=round(o.mean(), 2), overflow_p90=round(o.quantile(.9), 2),
                         benign_demotes=round(g.benign_demotes.mean(), 1),
                         attack_demotes=round(g.attack_demotes.mean(), 1),
                         decision_ms=round(1000 * g.decision_ms_mean.mean(), 3)))
    by = (att.pivot_table(index="defense", columns="variant", values="benign_flows_harmed_frac")
          * 100).round(2).reindex(DEFENSES)
    tests = []
    for m in METRICS:
        for b in DEFENSES[1:]:
            md, w, l, p = R1.cluster_wilcoxon(att, m, "v2.1", b)
            tests.append(dict(metric=m, baseline=b, mean_diff_mlp_minus=md, mlp_lower=w,
                              mlp_higher=l, p=p))
    return pd.DataFrame(rows), by, pd.DataFrame(tests)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "episodes.csv")
    t0 = time.time()
    if os.path.exists(path):
        df = pd.read_csv(path)
        print("episodes exist; reporting only")
    else:
        sel = json.load(open("results/v21/selected.json"))["selected"]
        v21._load_ctx("results/v2", "results/v21", sel)
        models, taus = train()
        _M.update(models=models, taus=taus, pol=v21._policy(sel))
        json.dump({f"{h}/{d}": t for (h, d), t in taus.items()},
                  open(os.path.join(OUT, "taus.json"), "w"), indent=1)
        print(f"[train] {time.time() - t0:.0f} s", flush=True)
        tasks = [(n, d, v, s) for n in DEFENSES for d in DOMAINS
                 for v in list(VARIANTS) + [None] for s in SEEDS]
        rows = []
        with get_context("fork").Pool(a.workers) as p:
            for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
                rows.append(row)
                if (i + 1) % 100 == 0:
                    print(f"  {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
    s, by, t = report(df)
    s.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    by.to_csv(os.path.join(OUT, "by_variant.csv"))
    t.to_csv(os.path.join(OUT, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s.to_string(index=False))
    print(by.to_string())
    print(t.round(5).to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
