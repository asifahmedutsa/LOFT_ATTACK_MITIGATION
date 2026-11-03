"""Preliminary table of finished campaign runs (reads summary.txt only; light enough to run
during a campaign). Means over the seeds present; n says how many. Not the preregistered
analysis.

    python3 testbed/prelim_table.py [--tag t1] [--seeds 4110 4111]
"""
import argparse
import glob
import os
import re
from collections import defaultdict

COLS = [("harm", "benign_harmed_pct"), ("lost1st", "benign_packet_in_lost_pct"),
        ("probe", "probe_post_success_pct"), ("att_s11", "attack_share_avg_pct_s11"),
        ("att_s12", "attack_share_avg_pct_s12"), ("att_s13", "attack_share_avg_pct_s13"),
        ("full_s", "overflow_s_post_s11")]


def read(path):
    out = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2:
            try:
                out[p[0]] = float(p[1])
            except ValueError:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=os.path.expanduser("~/loft-runs"))
    ap.add_argument("--tag", default="t1")
    ap.add_argument("--seeds", nargs="*", type=int)
    a = ap.parse_args()
    cells = defaultdict(list)
    for f in glob.glob(f"{a.runs}/{a.tag}_*/summary.txt"):
        m = re.match(rf"{a.tag}_([^_]+)_([^_]+)_(.+)_s(\d+)$", os.path.basename(os.path.dirname(f)))
        if not m or (a.seeds and int(m[4]) not in a.seeds):
            continue
        cells[(m[2], m[3])].append(read(f))
    print(f"{'variant':8} {'defense':28} n " + " ".join(f"{c:>8}" for c, _ in COLS))
    for (var, d), rows in sorted(cells.items()):
        vals = []
        for _, k in COLS:
            xs = [r[k] for r in rows if k in r]
            vals.append(f"{sum(xs) / len(xs):8.2f}" if xs else f"{'-':>8}")
        print(f"{var:8} {d:28} {len(rows)} " + " ".join(vals))


if __name__ == "__main__":
    main()
