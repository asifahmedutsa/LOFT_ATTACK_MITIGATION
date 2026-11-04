"""Collect the E5 testbed runs (testbed/matrix_e5.sh) into results/testbed_e5/.

    python3 testbed/collect_e5.py [tag [domain]]   # default e5c T1; other tags write results/testbed_<tag>/

Reads ~/loft-runs/<tag>_T1_<variant>_<defense>_s<seed>/summary.txt and writes runs.csv (one row
per run) and table_e5.csv / table_e5.md (mean and min-max over seeds per variant and defense).
"""
import csv
import glob
import os
import re
import statistics
import sys

TAG = sys.argv[1] if len(sys.argv) > 1 else "e5c"
DOM = sys.argv[2] if len(sys.argv) > 2 else "T1"
RUNS = os.path.expanduser("~/loft-runs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "testbed_e5" if TAG == "e5c" else f"testbed_{TAG}")
DEFENSES = ["none", "evict", "sift", "tableguard", "dms-btt", "ftmaster", "ftop", "rdefender", "dualguard", "dualguard+portguard",
            "dualguard+hold", "dualguard+portguard+hold", "dualguard+evict", "dualguard+fairevict",
            "dualguard+fairevictq", "dualguard+portguard+hostid", "portguard+hostid", "ensguard"]
KEYS = ["benign_harmed_pct", "probe_post_success_pct", "probe_post_connect_ms_median",
        "probe_post_connect_ms_p95", "probe_pre_success_pct", "entries_after_attack",
        "table_full", "packet_in", "installs", "deletes", "demotes", "evictions", "decision_ms",
        "seconds"]
SHOW = [("benign_harmed_pct", "benign harm %"), ("probe_post_success_pct", "probe success %"),
        ("probe_post_connect_ms_median", "probe connect ms (median)"),
        ("installs", "installs"), ("decision_ms", "decision ms (mean)")]


def parse(path):
    r = {}
    for line in open(path):
        m = re.match(r"\s+(\S+)\s+(.*)", line)
        if m and m.group(1) in KEYS:
            v = m.group(2).split()
            # "mean 836, max 1273" -> 836; "n/a" -> None; plain number -> number
            tok = v[1].rstrip(",") if v[0] == "mean" else v[0]
            try:
                r[m.group(1)] = float(tok)
            except ValueError:
                r[m.group(1)] = None
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for s in sorted(glob.glob(os.path.join(RUNS, f"{TAG}_{DOM}_*_s*/summary.txt"))):
        name = os.path.basename(os.path.dirname(s))
        _, dom, variant, defense, seed = name.split("_")
        rows.append(dict(domain=dom, variant=variant, defense=defense.replace("-", "+")
                         if defense.startswith("dualguard-") else defense,
                         seed=int(seed[1:]), **parse(s)))
    with open(os.path.join(OUT, "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["domain", "variant", "defense", "seed"] + KEYS)
        w.writeheader()
        w.writerows(rows)
    table, md = [], []
    for v in sorted({r["variant"] for r in rows}):
        md += [f"\n### {DOM}, {v}\n", "| defense | n | " + " | ".join(h for _, h in SHOW) + " |",
               "|---|---|" + "---|" * len(SHOW)]
        for d in DEFENSES:
            g = [r for r in rows if r["variant"] == v and r["defense"] == d]
            if not g:
                continue
            row, cells = dict(variant=v, defense=d, n=len(g)), []
            for k, _ in SHOW:
                x = [r[k] for r in g if r.get(k) is not None]
                if not x:
                    cells.append("n/a")
                    continue
                row[k + "_mean"] = round(statistics.mean(x), 2)
                row[k + "_min"], row[k + "_max"] = min(x), max(x)
                cells.append(f"{statistics.mean(x):.2f} ({min(x):g}-{max(x):g})")
            table.append(row)
            md.append(f"| {d} | {len(g)} | " + " | ".join(cells) + " |")
    with open(os.path.join(OUT, "table_e5.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, sorted({k for r in table for k in r}, key=lambda k: (k not in
                           ("variant", "defense", "n"), k)))
        w.writeheader()
        w.writerows(table)
    text = f"E5 testbed ({TAG}): mean (min-max) over seeds\n" + "\n".join(md) + "\n"
    open(os.path.join(OUT, "table_e5.md"), "w").write(text)
    print(text)
    print(len(rows), "runs")


if __name__ == "__main__":
    main()
