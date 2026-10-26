"""Reviewer probe: an adaptive attacker that refreshes faster than t_short.

    python -m loftbench.probe_adaptive --src results/v2 --v21 results/v21 --out results/review

Soft demotion reinstalls flagged flows with a 1 s idle timeout, which only
removes flows whose refresh gap exceeds 1 s. These variants refresh every
0.8-0.95 s (about 8x the packet rate of A1-A7) and are outside the declared
threat model; they test where the mechanism stops working. Not part of any
training, selection or reported test set.
"""
import os

# One BLAS thread per worker process (see experiment.py).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json

import pandas as pd

from . import v21
from .config import DOMAINS, AttackVariant, SimConfig
from .data import DOMAIN_IDX
from .sim import run_episode
from .traffic import build_traffic

ADAPTIVE = {
    "fast-refresh": AttackVariant("X1-fast", 100, (0.8, 0.95), size_mode="benign",
                                  src_mode="spoof", burst_pps=5000.0),
    "fast-mimic": AttackVariant("X2-fastmimic", 100, (0.8, 0.95), pkts_per_refresh=(1, 3),
                                size_mode="benign", src_mode="pool", burst_pps=8000.0),
}
DEFENSES = ["none", "dms-btt", "v2", "v2.1"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--v21", default="results/v21")
    ap.add_argument("--out", default="results/review")
    ap.add_argument("--seeds", default="5000,5001,5002")
    ap.add_argument("--domains", default=",".join(DOMAINS))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sel = json.load(open(os.path.join(a.v21, "selected.json")))["selected"]
    v21._load_ctx(a.src, a.v21, sel)
    cfg = SimConfig(duration=300.0)
    rows = []
    for vn, var in ADAPTIVE.items():
        for name in DEFENSES:
            for d in a.domains.split(","):
                for s in map(int, a.seeds.split(",")):
                    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], var, s, cfg.duration,
                                       cfg.attack_start)
                    r = run_episode(tr, cfg, v21._make(name, d, None), record_ts=False).summary
                    rows.append(dict(variant=vn, defense=name, domain=d, seed=s,
                                     impacted_pct=100 * r["benign_flows_impacted_frac"],
                                     attack_occ_pct=100 * r["avg_attack_occ_post"],
                                     overflow_s=r["overflow_seconds_post_attack"],
                                     attack_pps=r["attack_pkts"] / (cfg.duration - cfg.attack_start)))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.out, "probe_adaptive.csv"), index=False)
    print(df.groupby(["variant", "defense"])[
        ["impacted_pct", "attack_occ_pct", "overflow_s", "attack_pps"]].mean().round(2))


if __name__ == "__main__":
    main()
