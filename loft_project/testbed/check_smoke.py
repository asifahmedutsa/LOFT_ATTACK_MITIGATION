"""Smoke runs before the final campaign (testbed/campaign_smoke.sh): did each defense load, act and log?
Not results.

    python3 testbed/check_smoke.py     # writes results/testbed_prereg_final/smoke.md
"""
import glob
import os
import re

RUNS = os.path.expanduser("~/loft-runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "testbed_prereg_final", "smoke.md")
KEYS = ["seconds", "packet_in", "deletes", "hosts_blocked_attack", "hosts_blocked_benign", "sources_blocked_attack",
        "sources_blocked_benign", "drop_rules", "ingress_drops", "first_attack_block_s", "benign_harmed_pct",
        "benign_deleted_per_min", "probe_post_success_pct", "attack_share_avg_pct_s11"]


def summary(path):
    d = {}
    for line in open(path):
        r = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if r:
            d[r[1]] = r[2]
    return d


def main():
    L = ["# Smoke runs (seed 4183): load, act, log", "", "testbed/campaign_smoke.sh; not results. Acts: the defense "
         "deleted entries or blocked a host or source. Errors: Traceback lines in the controller log.", "",
         "| Run | Summary | Errors | " + " | ".join(KEYS) + " |", "|---|---|---|" + "---|" * len(KEYS)]
    for d in sorted(glob.glob(f"{RUNS}/smk_*")) + sorted(glob.glob(f"{RUNS}/_failed/smk_*")):
        if not os.path.isdir(d):
            continue
        s = os.path.join(d, "summary.txt")
        err = sum(open(p, errors="replace").read().count("Traceback") for p in glob.glob(f"{d}/ryu_*.log"))
        v = summary(s) if os.path.exists(s) else {}
        L.append(f"| {os.path.relpath(d, RUNS)} | {'yes' if v else 'no'} | {err} | " +
                 " | ".join(v.get(k, "-") for k in KEYS) + " |")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
