"""Reviewer probe: are benign flows counted as evicted/demoted still active?

    python -m loftbench.probe_harm --src results/v2 --v21 results/v21 --out results/review

benign_flows_impacted_frac counts a benign flow as impacted once any defense
deletes or demotes its entry, even if the flow never sends another packet
(its entry was stale and would have idled out). This probe records the first
time each benign entry is acted on and checks whether the flow has packets
after that time. Uses fresh-test seeds, so it reports only and selects nothing.
"""
import os

# One BLAS thread per worker process (see experiment.py).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json

import numpy as np
import pandas as pd

from . import v21
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .sim import run_episode
from .traffic import build_traffic

DEFENSES = ["dms-btt", "v2", "v2.1"]


def probe(name, d, v, s, cfg):
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v], s, cfg.duration, cfg.attack_start)
    pol = v21._make(name, d, None)
    first_act = {}
    orig = pol.on_poll

    def hook(t, obs):
        dels, dems = orig(t, obs)
        for arr in (dels, dems):
            if arr is not None:
                for f in np.asarray(arr):
                    if not tr.flow_attack[f] and f not in first_act:
                        first_act[f] = t
        return dels, dems

    pol.on_poll = hook
    r = run_episode(tr, cfg, pol, record_ts=False).summary
    last = np.zeros(tr.n_flows)
    np.maximum.at(last, tr.pkt_fid, tr.pkt_t)
    f = np.array(list(first_act), dtype=np.int64)
    t = np.array(list(first_act.values()))
    return dict(defense=name, domain=d, variant=v, seed=s,
                evicted_pct=100 * r["benign_flows_evicted_frac"], n_acted=len(f),
                frac_with_later_pkts=float((last[f] > t).mean()) if len(f) else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--v21", default="results/v21")
    ap.add_argument("--out", default="results/review")
    ap.add_argument("--variants", default="A1,A4,A6")
    ap.add_argument("--seeds", default="5000,5001")
    ap.add_argument("--domains", default=",".join(DOMAINS))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sel = json.load(open(os.path.join(a.v21, "selected.json")))["selected"]
    v21._load_ctx(a.src, a.v21, sel)
    cfg = SimConfig(duration=300.0)
    rows = [probe(n, d, v, int(s), cfg) for n in DEFENSES for d in a.domains.split(",")
            for v in a.variants.split(",") for s in a.seeds.split(",")]
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.out, "probe_harm.csv"), index=False)
    cols = ["evicted_pct", "n_acted", "frac_with_later_pkts"]
    print(df.groupby(["defense", "variant"])[cols].mean().round(3))
    print(df.groupby("defense")[cols].mean().round(3))


if __name__ == "__main__":
    main()
