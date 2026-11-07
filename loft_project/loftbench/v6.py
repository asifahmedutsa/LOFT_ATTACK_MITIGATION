"""FEVER v6 development check (docs/v6_plan.md): v5 and v6 (permanent blocking) in the simulator,
test-domain traffic T1B at the testbed's 600 pps, development seeds 2000-2002, A2 / A4 / E9P /
benign, each host on its own port (4 benign, 2 attackers). Both are built from the exported
configs exactly as the testbed controller builds them (testbed/loft_ryu_app.py); the volume limit
is the core switch's (s11), whose table sees every host as the simulator's single table does.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.v6

Writes results/v6/{episodes.csv, check.md}.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import dataclasses  # noqa: E402
import json  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import SimConfig, attack_variant  # noqa: E402
from .defenses import EvictBlock, PortGuard  # noqa: E402
from .ensjson import EnsembleJSON  # noqa: E402
from .ports import assign_ports  # noqa: E402
from .sim import run_episode  # noqa: E402
from .trace import TRACE_DOMAIN_IDX, TRACE_DOMAINS  # noqa: E402
from .traffic import build_traffic  # noqa: E402

OUT = "results/v6"
EXP = "results/v21/exported"
SEEDS = (2000, 2001, 2002)
VARS = ("A2", "A4", "E9P", "benign")
CFGS = {"v5": "ens_config_v5.json", "v6": "ens_config_v6.json", "fever": "ens_config_v6.json"}
ALL_CFGS = dict(CFGS, **{"fever-fl": "ens_config_fl.json"})   # fever-fl: federated XGBoost detector
N_BENIGN = 4
SW = "s11"


def make(key):
    ec = json.load(open(f"{EXP}/{ALL_CFGS[key]}"))
    pg = json.load(open(f"{EXP}/defenses.json"))["portguard"]
    b = ec["block"]
    eb = EvictBlock(EnsembleJSON(EXP, ec), ec["tau"]["T1B"], name="evictblock",
                    rho=ec["rho"]["T1B"], window_s=b["window_s"], n_min=b["n_min"],
                    f_min=b["k"], block_s=b["block_s"], m0=b.get("m0", 1.0), frac_min=b.get("frac_min", 0.0),
                    score_changed_only=bool(ec.get("score_changed_only", False)),
                    vol_x=b["vol_x"]["T1B"][SW], permanent=bool(b.get("permanent", False)))
    if key in ("fever", "fever-fl"):          # v6 without PortGuard
        return eb
    return PortGuard(eb, name=key, mode="full", **{k: pg[k] for k in pg if k != "mode"})


def _task(args):
    key, v, s = args
    prof = dataclasses.replace(TRACE_DOMAINS["T1B"], rate_pps=600.0)
    tr = assign_ports(build_traffic(prof, TRACE_DOMAIN_IDX["T1B"], None if v == "benign" else attack_variant(v),
                                    s, 300.0, 50.0), "dedicated")
    d = make(key)
    sm = run_episode(tr, SimConfig(duration=300.0), defense=d, record_ts=False).summary
    blocks = getattr(d, "inner", d).blocks
    att = [t for t, q in blocks if q >= N_BENIGN]
    return dict(defense=key, variant=v, seed=s, harm_pct=100 * sm["benign_flows_harmed_frac"],
                attack_occ_pct=100 * sm.get("avg_attack_occ_post", 0.0),
                benign_hosts_blocked=len({q for _, q in blocks if q < N_BENIGN}),
                attack_hosts_blocked=len({q for _, q in blocks if q >= N_BENIGN}),
                attack_blocks=len(att), first_block_s=min(att, default=np.nan) - 50.0)


def main():
    os.makedirs(OUT, exist_ok=True)
    tasks = [(k, v, s) for k in CFGS for v in VARS for s in SEEDS]
    with get_context("fork").Pool(4) as p:
        df = pd.DataFrame(p.map(_task, tasks, chunksize=1))
    df.sort_values(["variant", "seed", "defense"]).to_csv(f"{OUT}/episodes.csv", index=False)
    m = df.groupby(["variant", "defense"])[["harm_pct", "attack_occ_pct"]].mean()

    def g(v, k, c):
        return float(m.loc[(v, k), c])
    checks = [("A2: harm v6 <= v5", g("A2", "v6", "harm_pct") <= g("A2", "v5", "harm_pct")),
              ("A2: attack occupancy v6 <= v5", g("A2", "v6", "attack_occ_pct") <= g("A2", "v5", "attack_occ_pct"))]
    for v in ("A4", "E9P"):
        checks += [(f"{v}: harm v6 <= v5 + 0.1", g(v, "v6", "harm_pct") <= g(v, "v5", "harm_pct") + 0.1),
                   (f"{v}: attack occupancy v6 <= v5 + 2", g(v, "v6", "attack_occ_pct") <= g(v, "v5", "attack_occ_pct") + 2)]
    checks += [("No benign host blocked by v6", int(df[df.defense == "v6"].benign_hosts_blocked.sum()) == 0),
               ("Benign only: harm v6 <= 0.1 %", g("benign", "v6", "harm_pct") <= 0.1)]
    adopt = all(ok for _, ok in checks)
    L = ["# FEVER v6 development check (docs/v6_plan.md)", "",
         "Simulator, T1B at 600 pps, seeds 2000-2002, volume limit of s11. Means of three runs.", "",
         "| Traffic | Method | Harm % | Attack occupancy % | Benign hosts blocked | Attack blocks | First block (s after onset) |",
         "|---|---|---|---|---|---|---|"]
    for (v, k), r in df.groupby(["variant", "defense"]):
        L.append(f"| {v} | {k} | {r.harm_pct.mean():.3f} | {r.attack_occ_pct.mean():.2f} | "
                 f"{int(r.benign_hosts_blocked.sum())} | {r.attack_blocks.mean():.1f} | {r.first_block_s.mean():.1f} |")
    L += ["", "| Condition | Holds |", "|---|---|"] + [f"| {c} | {'yes' if ok else 'no'} |" for c, ok in checks]
    L += ["", f"**Adopt v6: {'yes' if adopt else 'no'}.**"]
    open(f"{OUT}/check.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
