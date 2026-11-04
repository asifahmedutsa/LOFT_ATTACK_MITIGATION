"""E10 (docs/other_papers_run_plan.md): overhead of each defense, descriptive, no new runs.

testbed   the 54 E5 runs (~/loft-runs/e5c_T1_*): controller (Ryu, python3.8) and ovs-vswitchd CPU
          from pidstat (1 s samples; before / after the first 50 s, the attack start), controller
          decision time per Packet-In batch and its worst second, peak event backlog, Packet-In
          and flow-mods. Mean over 3 seeds per attack and defense.
simulator E3's episodes (600 s, D1-D3 and T1, A1-A7): decision time per poll (mean, p99),
          Packet-In and flow-mods per episode.
size      each defense's state as pickled bytes (models and thresholds), D1 and T1.
FL        DualGuard's federated training traffic (results/v21/train_info.json).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e10_overhead

Writes results/e10_overhead/.
"""
import collections
import csv
import glob
import json
import os
import pickle

import numpy as np
import pandas as pd

from . import e3_main as E3
from .config import VARIANTS
from .experiment import _dump

OUT = "results/e10_overhead"
RUNS = os.path.expanduser("~/loft-runs")
ATTACK_S = 50
PROC = {"python3.8": "controller", "ovs-vswitchd": "switch"}


def _cpu(path):
    v = collections.defaultdict(list)
    for line in open(path):
        p = line.split()
        if len(p) == 11 and p[3].isdigit() and p[-1] in PROC:
            v[PROC[p[-1]]].append(float(p[8]))
    out = {}
    for k, x in v.items():
        x = np.array(x)
        out[f"{k}_cpu_pre"] = x[:ATTACK_S].mean()
        out[f"{k}_cpu_attack"] = x[ATTACK_S:].mean()
        out[f"{k}_cpu_p95"] = np.percentile(x[ATTACK_S:], 95)
    return out


def testbed():
    rows = []
    for d in sorted(glob.glob(os.path.join(RUNS, "e5c_T1_*_s*"))):
        if not os.path.isdir(d):
            continue
        _, _, variant, defense, seed = os.path.basename(d).split("_")
        c = pd.read_csv(os.path.join(d, "controller_T1.csv"))
        last = c.iloc[-1]
        rows.append(dict(variant=variant, defense=defense.replace("-", "+")
                         if defense.startswith("dualguard-") else defense, seed=int(seed[1:]),
                         decision_ms=c.decision_ms.mean(), decision_ms_worst_s=c.decision_ms.max(),
                         backlog_max=c.event_backlog.max(), packet_in=last.packet_in,
                         flow_mods=last.installs + last.deletes + last.demotes,
                         **_cpu(os.path.join(d, "cpu_pidstat.txt"))))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "testbed_runs.csv"), index=False)
    return df


def simulator():
    df = pd.read_csv(os.path.join(E3.OUT, "test_episodes.csv"))
    df = df[df.variant.isin(VARIANTS)]
    t = df.groupby("defense")[["decision_ms_mean", "decision_ms_p99", "packet_in", "flow_mods"]].mean()
    return t.reindex(E3.DEFENSES)


def sizes():
    E3._load()
    rows = []
    for n in E3.DEFENSES:
        r = {"defense": n}
        for d in ("D1", "T1"):
            try:
                r[f"bytes_{d}"] = len(pickle.dumps(E3._make(n, d)))
            except Exception as e:  # noqa: BLE001 - unpicklable state is reported, not fatal
                r[f"bytes_{d}"] = f"n/a ({type(e).__name__})"
        rows.append(r)
    return pd.DataFrame(rows).set_index("defense")


def main():
    os.makedirs(OUT, exist_ok=True)
    tb = testbed()
    cols = ["controller_cpu_pre", "controller_cpu_attack", "controller_cpu_p95", "switch_cpu_attack",
            "decision_ms", "decision_ms_worst_s", "backlog_max", "packet_in", "flow_mods"]
    tbt = tb.groupby(["variant", "defense"])[cols].mean().round(1)
    tbt.to_csv(os.path.join(OUT, "table_testbed.csv"))
    sim = simulator().round(2)
    sim.to_csv(os.path.join(OUT, "table_simulator.csv"))
    sz = sizes()
    sz.to_csv(os.path.join(OUT, "table_size.csv"))
    fl = json.load(open("results/v21/train_info.json"))["fedavg_noctx_comm"]
    _dump(OUT, "fl_comm.json", fl)
    pd.set_option("display.width", 250)
    print(tbt.to_string())
    print(sim.to_string())
    print(sz.to_string())
    print(json.dumps(fl))


if __name__ == "__main__":
    main()
