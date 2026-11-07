"""FEVER ablation (docs/fever_ablation_plan.md): FEVER, FEVER without the volume block and FEVER
without the detector, on the seeds all three have.

    python3 testbed/analyze_ablation.py      # writes results/fever_ablation/{runs.csv, report.md}
"""
import csv
import os
import re

R = os.path.expanduser("~/loft-runs")
OUT = "results/fever_ablation"
ATTACKS = ["A2", "A4", "E9P"]
VARS = [("ensguard-v5", "FEVER"), ("ensguard-v4lite", "FEVER without volume"),
        ("ensguard-v5-noml", "FEVER without ML")]
KEYS = ["benign_harmed_pct", "attack_share_avg_pct_s11", "benign_packet_in_lost_pct", "probe_post_success_pct",
        "hosts_blocked_attack", "hosts_blocked_benign", "first_attack_block_s", "decision_ms_mean"]


def summary(path):
    d = {}
    for line in open(path):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not m:
            continue
        k, v = m[1], m[2]
        if k == "decision_ms":
            d["decision_ms_mean"] = float(re.match(r"mean (\S+),", v)[1])
            continue
        try:
            d[k] = float(v)
        except ValueError:
            d[k] = v
    for k in ("hosts_blocked_attack", "hosts_blocked_benign"):
        d.setdefault(k, 0.0)
    return d


def path(v, d, s):
    return f"{R}/v5_T1B_{v}_{d}_s{s}/summary.txt"


seeds = [s for s in range(4140, 4145)
         if all(os.path.exists(path(v, d, s)) for v in ATTACKS + ["benign"] for d, _ in VARS)]
assert seeds, "no seed has all three variants"
runs = {(v, d, s): summary(path(v, d, s)) for v in ATTACKS + ["benign"] for d, _ in VARS for s in seeds}
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/runs.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["variant", "defense", "seed"] + KEYS)
    for (v, d, s), r in sorted(runs.items()):
        w.writerow([v, d, s] + [r.get(k, "") for k in KEYS])


def mean(v, d, k):
    xs = [r.get(k) for (vv, dd, _), r in runs.items() if vv == v and dd == d]
    xs = [float(x) for x in xs if isinstance(x, (int, float))]
    return sum(xs) / len(xs) if xs else float("nan")


L = ["# FEVER ablation on the testbed (exploratory)", "",
     f"Plan: docs/fever_ablation_plan.md. T1B, seeds {', '.join(map(str, seeds))}. FEVER and FEVER without "
     "volume are the v5-campaign runs; FEVER without ML is new. Means over seeds.", "",
     "| Attack | Variant | harm % | attack share s11 % | lost first pkts % | probe success % | attackers blocked | "
     "benign blocked | first attacker block (s) | decision ms |", "|---|---|---|---|---|---|---|---|---|---|"]
for v in ATTACKS + ["benign"]:
    for d, name in VARS:
        L.append(f"| {v} | {name} | {mean(v, d, 'benign_harmed_pct'):.2f} | {mean(v, d, 'attack_share_avg_pct_s11'):.1f} | "
                 f"{mean(v, d, 'benign_packet_in_lost_pct'):.1f} | {mean(v, d, 'probe_post_success_pct'):.1f} | "
                 f"{mean(v, d, 'hosts_blocked_attack'):.1f} | {mean(v, d, 'hosts_blocked_benign'):.1f} | "
                 f"{mean(v, d, 'first_attack_block_s'):.0f} | {mean(v, d, 'decision_ms_mean'):.0f} |")
L += ["", "## Paired wins of FEVER (lower is better), per attack", "",
      "| Against | Measure | A2 | A4 | E9P | all |", "|---|---|---|---|---|---|"]
for d, name in VARS[1:]:
    for k, kn in (("benign_harmed_pct", "harm"), ("attack_share_avg_pct_s11", "attack share")):
        cells, tw, tn = [], 0, 0
        for v in ATTACKS:
            w = sum(runs[(v, "ensguard-v5", s)][k] < runs[(v, d, s)][k] for s in seeds)
            cells.append(f"{w}/{len(seeds)}")
            tw, tn = tw + w, tn + len(seeds)
        L.append(f"| {name} | {kn} | " + " | ".join(cells) + f" | {tw}/{tn} |")
L += ["", "## Every run", "", "| Seed | Attack | Variant | harm % | share % | attackers blocked | benign blocked | first block (s) |",
      "|---|---|---|---|---|---|---|---|"]
for s in seeds:
    for v in ATTACKS + ["benign"]:
        for d, name in VARS:
            r = runs[(v, d, s)]
            L.append(f"| {s} | {v} | {name} | {r['benign_harmed_pct']:.2f} | {float(r.get('attack_share_avg_pct_s11', 0)):.1f} | "
                     f"{int(r['hosts_blocked_attack'])} | {int(r['hosts_blocked_benign'])} | {r.get('first_attack_block_s', '-')} |")
open(f"{OUT}/report.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
