"""Tune DualGuard policy knobs on validation runs only (never on test seeds).

    python -m loftbench.tune --out results/v2

Grid over (rho, t_short); selects the setting minimizing mean benign-flows-
impacted on attacked validation episodes, subject to mean malicious
occupancy after onset <= 15%. The chosen knobs are applied identically to
every detector that uses the DualGuard policy.
"""
import os

# One BLAS thread per worker process; multithreaded BLAS across worker
# processes oversubscribes the CPU (measured ~17x slower inference).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import itertools
from multiprocessing import get_context

import pandas as pd
import pickle

from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DualGuard
from .experiment import SPLITS, _dump
from .sim import run_episode
from .traffic import build_traffic

# OpenFlow idle_timeout is an integer number of seconds, so only t_short >= 1
# is deployable; sub-second values are kept for analysis only.
GRID = dict(rho=[0.3, 0.5, 0.7], t_short=[0.5, 1.0, 2.0])
DEPLOYABLE_T_SHORT = (1.0, 2.0)
_M = None


def _task(args):
    rho, ts, d, v, s = args
    models, taus = _M
    cfg = SimConfig(duration=300.0)
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       cfg.duration, cfg.attack_start)
    pol = DualGuard(models["fedprox"], taus[f"fedprox/{d}"], rho=rho, t_short=ts)
    r = run_episode(tr, cfg, pol, record_ts=False).summary
    return dict(rho=rho, t_short=ts, domain=d, variant=v or "benign", seed=s,
                impacted=r["benign_flows_impacted_frac"], att_occ=r["avg_attack_occ_post"])


def main():
    global _M
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/v2")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--select-only", action="store_true")
    a = ap.parse_args()
    csv_path = os.path.join(a.out, "tuning_validation.csv")
    if a.select_only:
        select(a.out, pd.read_csv(csv_path))
        return
    _M = pickle.load(open(os.path.join(a.out, "models.pkl"), "rb"))
    tasks = [(r, t, d, v, s) for r, t in itertools.product(GRID["rho"], GRID["t_short"])
             for d in DOMAINS for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
    with get_context("fork").Pool(a.workers) as p:
        rows = []
        for i, r in enumerate(p.imap_unordered(_task, tasks, chunksize=2)):
            rows.append(r)
            if (i + 1) % 100 == 0:
                print(f"  [tune] {i + 1}/{len(tasks)}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    select(a.out, df)


def select(out, df):
    g = df[df.variant != "benign"].groupby(["rho", "t_short"])[["impacted", "att_occ"]].mean()
    print(g)
    ok = g[(g.att_occ <= 0.15) & g.index.get_level_values("t_short").isin(DEPLOYABLE_T_SHORT)]
    best = ok.impacted.idxmin() if len(ok) else g.att_occ.idxmin()
    _dump(out, "tuned_policy.json", dict(rho=float(best[0]), t_short=float(best[1]), grid=GRID,
                                         deployable_t_short=DEPLOYABLE_T_SHORT,
                                         table=g.reset_index().to_dict("records")))
    print("selected", best)


if __name__ == "__main__":
    main()
