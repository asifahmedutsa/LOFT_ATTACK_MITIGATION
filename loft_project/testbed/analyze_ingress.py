"""Development check of docs/ingress_plan.md: fever-fl-ll (ingress blocking) against
fever-fl-ll-noing (the old block) on seeds 4181-4182, and FTMaster's source blocks on E9P.

    python3 testbed/analyze_ingress.py     # writes results/tbfl/ingress_check.md

Attack occupancy: attack share of the table after onset, averaged over the three switches.
"""
import os
import re

RUNS = os.path.expanduser("~/loft-runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "tbfl", "ingress_check.md")
VARS, SEEDS, ATT = ["A2", "A4", "E9P", "benign"], [4181, 4182], ["A2", "A4", "E9P"]
NEW, OLD = "fever-fl-ll", "fever-fl-ll-noing"
COLS = [("benign_harmed_pct", "Harm %", 3), ("occ", "Attack occupancy %", 2),
        ("probe_post_success_pct", "Probe success %", 1), ("benign_never_installed_pct", "Never installed %", 2),
        ("packet_in", "Packet-Ins", 0), ("drop_rules", "Drop rules", 0), ("ingress_drops", "Ingress rules", 0),
        ("first_attack_block_s", "First block s", 1), ("hosts_blocked_benign", "Benign hosts blocked", 1)]


def summary(path):
    """summary.txt of one run -> {key: value}, as in analyze_flcheck.py."""
    d = {}
    for line in open(path):
        r = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not r:
            continue
        try:
            d[r[1]] = float(r[2])
        except ValueError:
            d[r[1]] = r[2]
    for k in ("hosts_blocked_attack", "hosts_blocked_benign", "ingress_drops", "sources_blocked_attack",
              "sources_blocked_benign"):
        d.setdefault(k, 0.0)            # written only when non-zero
    d["occ"] = sum(d.get(f"attack_share_avg_pct_s1{k}", 0.0) for k in (1, 2, 3)) / 3
    return d


def mean(runs, k):
    x = [r[k] for r in runs if isinstance(r.get(k), float)]
    return sum(x) / len(x) if x else float("nan")


m = {}
for v in VARS:
    for de in (OLD, NEW):
        got = [summary(p) for s in SEEDS
               for p in [os.path.join(RUNS, f"ing_T1B_{v}_{de}_s{s}", "summary.txt")] if os.path.exists(p)]
        if got:
            m[(v, de)] = got
L = ["# FEVER with ingress blocking: development check", "",
     "T1B at 600 pps, tree, seeds 4181-4182 (docs/ingress_plan.md). fever-fl-ll-noing: the old block",
     "(2 s drop rule renewed by the blocking switch); fever-fl-ll: permanent drop at the host's access",
     "port. Means of the runs; two seeds, so the columns after the attack occupancy are descriptive.", "",
     "| Traffic | Method | Runs | " + " | ".join(c[1] for c in COLS) + " |",
     "|---|---|---|" + "---|" * len(COLS)]
for v in VARS:
    for de in (OLD, NEW):
        if (v, de) in m:
            r = m[(v, de)]
            L.append(f"| {v} | {de} | {len(r)} | " + " | ".join(f"{mean(r, k):.{n}f}" for k, _, n in COLS) + " |")
complete = all(len(m.get((v, de), [])) == len(SEEDS) for v in VARS for de in (OLD, NEW))
if complete:
    checks = []
    for v in ATT:
        checks += [(f"{v}: harm ingress <= old + 0.1",
                    mean(m[(v, NEW)], "benign_harmed_pct") <= mean(m[(v, OLD)], "benign_harmed_pct") + 0.1),
                   (f"{v}: attack occupancy ingress <= old + 2", mean(m[(v, NEW)], "occ") <= mean(m[(v, OLD)], "occ") + 2)]
    checks += [("No benign host blocked by ingress", sum(r["hosts_blocked_benign"] for v in VARS for r in m[(v, NEW)]) == 0),
               ("Benign only: harm ingress <= 0.1 %", mean(m[("benign", NEW)], "benign_harmed_pct") <= 0.1)]
    ok = all(c for _, c in checks)
    L += ["", "## Adoption rule", "", "| Condition | Holds |", "|---|---|"]
    L += [f"| {c} | {'yes' if h else 'no'} |" for c, h in checks]
    L += ["", f"**{'Adopted: FEVER blocks at the ingress.' if ok else 'Not adopted: FEVER keeps the old block.'}**"]
else:
    L += ["", "Incomplete: not every run has a summary."]
ft = [summary(p) for s in SEEDS for p in [os.path.join(RUNS, f"ing_T1B_E9P_ftmaster_s{s}", "summary.txt")]
      if os.path.exists(p)]
if ft:
    L += ["", "## FTMaster's source blocks in the switch (E9P)", "",
          "| Runs | Sources blocked (attack) | Sources blocked (benign) | Drop rules | Packet-Ins | Probe success % | Harm % |",
          "|---|---|---|---|---|---|---|",
          f"| {len(ft)} | {mean(ft, 'sources_blocked_attack'):.1f} | {mean(ft, 'sources_blocked_benign'):.1f} | "
          f"{mean(ft, 'drop_rules'):.0f} | {mean(ft, 'packet_in'):.0f} | {mean(ft, 'probe_post_success_pct'):.1f} | "
          f"{mean(ft, 'benign_harmed_pct'):.3f} |"]
open(OUT, "w").write("\n".join(L) + "\n")
print("\n".join(L))
