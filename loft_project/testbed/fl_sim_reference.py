"""Simulator reference for the testbed's local-vs-federated runs (testbed/matrix_fl.sh).

Same traffic as the testbed (dedicated ports), same v2.1 policy; only the detector differs:
the federated FedAvg model or the controller's own local model. Seed 4000 (the testbed seed)
and seeds 8000-8009 (range).

  PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fl_sim_reference.py
"""
import csv
import json
from multiprocessing import get_context

from loftbench import v21
from loftbench.config import DOMAINS, VARIANTS, SimConfig
from loftbench.data import DOMAIN_IDX
from loftbench.defenses import DualGuard
from loftbench.ports import assign_ports
from loftbench.sim import run_episode
from loftbench.traffic import build_traffic

# Per controller: the first-listed exposure of each other controller, and A6 (unseen by all).
CELLS = {"D1": ["A2", "A3", "A6"], "D2": ["A1", "A3", "A6"], "D3": ["A1", "A2", "A6"]}
SEEDS = [4000] + list(range(8000, 8010))
OUT = "results/testbed_fl/sim_reference.csv"


def episode(args):
    model, d, v, s = args
    models, taus, _, sel = v21._CTX
    key = sel["detector"] if model == "federated" else f"local/{d}"
    dg = DualGuard(models[key], taus[f"{key.split('/')[0]}/{d}"], **v21._policy(sel))
    cfg = SimConfig(duration=300.0)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v], s, cfg.duration,
                                    cfg.attack_start), "dedicated")
    r = run_episode(tr, cfg, dg, record_ts=False).summary
    return dict(model=model, domain=d, variant=v, seed=s,
                harmed=100 * r["benign_flows_harmed_frac"], attack_demotes=r["attack_demotes"],
                benign_demotes=r["benign_demotes"], table_full=r["table_full"])


def main():
    sel = json.load(open("results/v21/selected.json"))["selected"]
    v21._load_ctx("results/v2", "results/v21", sel)
    tasks = [(m, d, v, s) for m in ("federated", "local") for d, vs in CELLS.items()
             for v in vs for s in SEEDS]
    with get_context("fork").Pool(4) as p:
        rows = p.map(episode, tasks, chunksize=2)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} episodes -> {OUT}")


if __name__ == "__main__":
    main()
