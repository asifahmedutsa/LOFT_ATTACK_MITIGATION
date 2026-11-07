"""FEVER v6 (permanent blocking, docs/v6_plan.md) against v5 and the published methods on the
v5-campaign seeds 4140-4144, run by run.

    python3 testbed/analyze_v6.py      # writes results/v6/{runs.csv, report.md}
"""
import csv
import os
import re



def summary(path):
    """summary.txt of one run -> {key: value}, as in analyze_ablation.py."""
    d = {}
    for line in open(path):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not m:
            continue
        if m[1] == "decision_ms":
            d["decision_ms_mean"] = float(re.match(r"mean (\S+),", m[2])[1])
            continue
        try:
            d[m[1]] = float(m[2])
        except ValueError:
            d[m[1]] = m[2]
    for k in ("hosts_blocked_attack", "hosts_blocked_benign"):
        d.setdefault(k, 0.0)            # written only when a host was blocked
    return d


R = os.path.expanduser("~/loft-runs")
OUT = "results/v6"
SEEDS = range(4140, 4145)
VARS = ["A2", "A4", "E9P", "benign"]
DEFS = [("ensguard-v6", "FEVER v6"), ("ensguard-v5", "FEVER v5"), ("dms-btt", "DMS-BTT"), ("ftmaster", "FTMaster")]
KEYS = [("benign_harmed_pct", "Harm %"), ("attack_share_avg_pct_s11", "Avg attack share %"),
        ("attack_share_max_pct_s11", "Max attack share %"), ("benign_packet_in_lost_pct", "First packets lost %"),
        ("probe_post_success_pct", "New connections ok %"), ("hosts_blocked_benign", "Benign hosts blocked")]

# runs.csv: the columns of results/testbed_prereg_v5/runs.csv, for the figure and table builders
ALL = ["benign_harmed_pct", "attack_share_avg_pct_s11", "attack_share_max_pct_s11", "benign_packet_in_lost_pct",
       "benign_dropped_by_rule_pct", "probe_post_success_pct", "probe_post_connect_ms_median",
       "hosts_blocked_attack", "hosts_blocked_benign", "first_attack_block_s", "decision_ms_mean",
       "packet_in", "table_full_s11", "overflow_s_post_s11"]
runs = {(v, d, s): summary(f"{R}/v5_T1B_{v}_{d}_s{s}/summary.txt")
        for v in VARS for d in [x for x, _ in DEFS] + ["none"] for s in SEEDS}
with open(f"{OUT}/runs.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["variant", "defense", "seed"] + ALL)
    for (v, d, s), r in sorted(runs.items()):
        w.writerow([v, d, s] + [r.get(k, "") for k in ALL])


def vals(vs, d, k):
    return [float(runs[(v, d, s)].get(k, 0) or 0) for v in vs for s in SEEDS]


def mean(xs):
    return sum(xs) / len(xs)


L = ["# FEVER v6 on the testbed (T1B, seeds 4140-4144, 5 runs per cell)", ""]
for title, vs in [("A2", ["A2"]), ("A4", ["A4"]), ("E9P", ["E9P"]), ("A2 + A4 + E9P", ["A2", "A4", "E9P"]),
                  ("Benign only", ["benign"])]:
    L += [f"## {title}", "", "| Method | " + " | ".join(n for _, n in KEYS) + " |", "|---" * (len(KEYS) + 1) + "|"]
    for d, n in DEFS:
        L.append(f"| {n} | " + " | ".join(f"{mean(vals(vs, d, k)):.2f}" for k, _ in KEYS) + " |")
    L.append("")
L += ["## v6 against v5, run by run (attack runs)", "", "| Metric | v6 better | equal | v5 better |", "|---|---|---|---|"]
for k, n in KEYS[:5]:
    hi = k == "probe_post_success_pct"
    a = vals(["A2", "A4", "E9P"], "ensguard-v6", k)
    b = vals(["A2", "A4", "E9P"], "ensguard-v5", k)
    better = sum((x > y) if hi else (x < y) for x, y in zip(a, b))
    eq = sum(abs(x - y) < 1e-9 for x, y in zip(a, b))
    L.append(f"| {n} | {better} | {eq} | {len(a) - better - eq} |")
open(f"{OUT}/report.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
