"""Deployment check (docs/testbed_training_plan.md): fever-fl against fever on seeds 4181-4182.

    python3 testbed/analyze_flcheck.py     # writes results/tbfl/flcheck.md

Attack occupancy: attack share of the table, mean over the run after onset, averaged over the
three switches (attack_share_avg_pct_s11-s13 of summarize_run.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_v6 import summary  # noqa: E402

RUNS = os.path.expanduser("~/loft-runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "tbfl", "flcheck.md")
VARS, DEFS, SEEDS = ["A2", "A4", "E9P", "benign"], ["fever", "fever-fl"], [4181, 4182]


def occ(d):
    return sum(d.get(f"attack_share_avg_pct_s1{k}", 0.0) for k in (1, 2, 3)) / 3


rows, m = [], {}
for v in VARS:
    for de in DEFS:
        got = []
        for s in SEEDS:
            p = os.path.join(RUNS, f"flc_T1B_{v}_{de}_s{s}", "summary.txt")
            if os.path.exists(p):
                d = summary(p)
                got.append((d["benign_harmed_pct"], occ(d), d["hosts_blocked_benign"], d["hosts_blocked_attack"]))
        if got:
            m[(v, de)] = [sum(x[i] for x in got) / len(got) for i in range(4)] + [len(got)]
L = ["# Deployment check: FEVER with the testbed-trained detector (fever-fl) against v6 (fever)", "",
     "T1B at 600 pps, seeds 4181-4182, testbed. Means of the runs.", "",
     "| Traffic | Method | Runs | Harm % | Attack occupancy % | Benign hosts blocked | Attack hosts blocked |",
     "|---|---|---|---|---|---|---|"]
for (v, de), r in sorted(m.items()):
    L.append(f"| {v} | {de} | {r[4]} | {r[0]:.3f} | {r[1]:.2f} | {r[2]:.1f} | {r[3]:.1f} |")
checks, complete = [], all((v, de) in m and m[(v, de)][4] == len(SEEDS) for v in VARS for de in DEFS)
if complete:
    for v in ("A2", "A4", "E9P"):
        checks += [(f"{v}: harm fever-fl <= fever + 0.1", m[(v, "fever-fl")][0] <= m[(v, "fever")][0] + 0.1),
                   (f"{v}: attack occupancy fever-fl <= fever + 2", m[(v, "fever-fl")][1] <= m[(v, "fever")][1] + 2)]
    checks += [("No benign host blocked by fever-fl", sum(m[(v, "fever-fl")][2] for v in VARS) == 0),
               ("Benign only: harm fever-fl <= 0.1 %", m[("benign", "fever-fl")][0] <= 0.1)]
    L += ["", "| Condition | Holds |", "|---|---|"] + [f"| {c} | {'yes' if ok else 'no'} |" for c, ok in checks]
    L += ["", f"**Deployment check passes: {'yes' if all(ok for _, ok in checks) else 'no'}.**"]
else:
    L += ["", "Incomplete: not every run has a summary."]
open(OUT, "w").write("\n".join(L) + "\n")
print("\n".join(L))
