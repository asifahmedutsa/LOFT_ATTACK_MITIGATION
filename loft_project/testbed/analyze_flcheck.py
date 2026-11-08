"""Deployment check (docs/testbed_training_plan.md, amendment 1): fever-fl-bag and fever-fl-ll
against fever on seeds 4181-4182.

    python3 testbed/analyze_flcheck.py     # writes results/tbfl/flcheck.md

Attack occupancy: attack share of the table, mean over the run after onset, averaged over the
three switches (attack_share_avg_pct_s11-s13 of summarize_run.py).
"""
import os
import re

RUNS = os.path.expanduser("~/loft-runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "tbfl", "flcheck.md")
VARS, SEEDS = ["A2", "A4", "E9P", "benign"], [4181, 4182]
BASE = "fever"
ARMS = {"fever-fl-bag": "Flower XGBoost bagging", "fever-fl-ll": "lossless federated XGBoost"}
DEFS = [BASE] + list(ARMS)
ATT = ["A2", "A4", "E9P"]


def summary(path):
    """summary.txt of one run -> {key: value}, as in analyze_v6.py (not imported: it runs on import)."""
    d = {}
    for line in open(path):
        r = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not r:
            continue
        try:
            d[r[1]] = float(r[2])
        except ValueError:
            d[r[1]] = r[2]
    for k in ("hosts_blocked_attack", "hosts_blocked_benign"):
        d.setdefault(k, 0.0)            # written only when a host was blocked
    return d


def occ(d):
    return sum(d.get(f"attack_share_avg_pct_s1{k}", 0.0) for k in (1, 2, 3)) / 3


m = {}
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
L = ["# Deployment check: FEVER with detectors trained on testbed rows by federated learning", "",
     "T1B at 600 pps, seeds 4181-4182, testbed. fever: v6 as deployed; fever-fl-bag: Flower XGBoost",
     "bagging; fever-fl-ll: lossless federated XGBoost. Means of the runs.", "",
     "| Traffic | Method | Runs | Harm % | Attack occupancy % | Benign hosts blocked | Attack hosts blocked |",
     "|---|---|---|---|---|---|---|"]
for v in VARS:
    for de in DEFS:
        if (v, de) in m:
            r = m[(v, de)]
            L.append(f"| {v} | {de} | {r[4]} | {r[0]:.3f} | {r[1]:.2f} | {r[2]:.1f} | {r[3]:.1f} |")
complete = all((v, de) in m and m[(v, de)][4] == len(SEEDS) for v in VARS for de in DEFS)
if complete:
    passed = {}
    for a in ARMS:
        checks = []
        for v in ATT:
            checks += [(f"{v}: harm {a} <= fever + 0.1", m[(v, a)][0] <= m[(v, BASE)][0] + 0.1),
                       (f"{v}: attack occupancy {a} <= fever + 2", m[(v, a)][1] <= m[(v, BASE)][1] + 2)]
        checks += [(f"No benign host blocked by {a}", sum(m[(v, a)][2] for v in VARS) == 0),
                   (f"Benign only: harm {a} <= 0.1 %", m[("benign", a)][0] <= 0.1)]
        passed[a] = all(ok for _, ok in checks)
        L += ["", f"## {a} ({ARMS[a]})", "", "| Condition | Holds |", "|---|---|"]
        L += [f"| {c} | {'yes' if ok else 'no'} |" for c, ok in checks]
        L += ["", f"**Passes: {'yes' if passed[a] else 'no'}.**"]
    mo = {a: sum(m[(v, a)][1] for v in ATT) / len(ATT) for a in ARMS}
    L += ["", "## Deployed detector (amendment 1)", "",
          "Mean attack occupancy over A2, A4, E9P: " + ", ".join(f"{a} {mo[a]:.2f} %" for a in ARMS) + "."]
    ok = [a for a in ARMS if passed[a]]
    if len(ok) == 2:
        pick = "fever-fl-bag" if abs(mo["fever-fl-bag"] - mo["fever-fl-ll"]) <= 1 else min(ok, key=mo.get)
    else:
        pick = ok[0] if ok else None
    L += ["", f"**{pick} ({ARMS[pick]}).**" if pick else
          "**Neither arm passes: rule A is re-tuned for each and checked on seed 4183.**"]
else:
    L += ["", "Incomplete: not every run has a summary."]
open(OUT, "w").write("\n".join(L) + "\n")
print("\n".join(L))
