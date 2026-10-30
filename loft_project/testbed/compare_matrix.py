"""Minimal testbed matrix (testbed/matrix_minimal.sh) against the simulator, cell by cell.

  python3 testbed/compare_matrix.py [--runs ~/loft-runs] [--out results/testbed_m1]

Simulator references: dedicated-port test episodes of revision 4b (D1-D3, seeds 8000-8009)
and revision 5 (T1, seeds 9000-9009); mean and range of benign flows harmed over the seeds.
Writes table_m1.csv and prints a Markdown table.
"""
import argparse
import csv
import os
import re

TB2SIM = {"none": "none", "dms-btt": "dms-blocklist", "dualguard": "v2.1",
          "dualguard_portguard": "v2.1+pfs4b"}


def sim_refs(root):
    ref = {}
    for rev, scen in (("revision4b", "dedicated"), ("revision5", None)):
        for r in csv.DictReader(open(os.path.join(root, "results", rev, "test_episodes.csv"))):
            if scen and r["scenario"] != scen:
                continue
            ref.setdefault((r["domain"], r["variant"], r["defense"]), []).append(
                100 * float(r["benign_flows_harmed_frac"]))
    return ref


def summary(path):
    s = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2 and re.fullmatch(r"[a-z_]+", p[0]):
            try:
                s.setdefault(p[0], float(p[1]))
            except ValueError:
                pass
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=os.path.expanduser("~/loft-runs"))
    ap.add_argument("--out", default="results/testbed_m1")
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ref = sim_refs(root)
    rows = []
    for name in sorted(os.listdir(a.runs)):
        m = re.fullmatch(r"m1_(D\d|T\d)_(A\d|X[\d.]+|benign)_(.+)_s(\d+)", name)
        if not m or not os.path.exists(os.path.join(a.runs, name, "summary.txt")):
            continue
        d, v, f, seed = m.groups()
        s = summary(os.path.join(a.runs, name, "summary.txt"))
        sim = ref.get((d, v, TB2SIM[f]), [])
        rows.append(dict(
            domain=d, variant=v, defense=f, seed=seed,
            tb_harmed=s.get("benign_harmed_pct"), tb_packet_in_lost=s.get("benign_packet_in_lost_pct"),
            tb_impact=s.get("benign_impact_pct"), tb_table_full=s.get("table_full"),
            sim_mean=round(sum(sim) / len(sim), 2) if sim else "",
            sim_min=round(min(sim), 2) if sim else "", sim_max=round(max(sim), 2) if sim else "",
            sim_n=len(sim)))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "table_m1.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("| Domain | Variant | Defense | Seed | Testbed harmed % | Simulator mean [min, max] | "
          "Packet-In lost % | TABLE_FULL |")
    print("|---|---|---|---|---|---|---|---|")
    order = {k: i for i, k in enumerate(TB2SIM)}
    for r in sorted(rows, key=lambda r: (r["variant"] == "benign", r["variant"].startswith("X"),
                                         r["seed"], r["variant"], r["domain"], order[r["defense"]])):
        sim = f"{r['sim_mean']} [{r['sim_min']}, {r['sim_max']}]" if r["sim_n"] else "—"
        print(f"| {r['domain']} | {r['variant']} | {r['defense']} | {r['seed']} | {r['tb_harmed']} | "
              f"{sim} | {r['tb_packet_in_lost']} | {int(r['tb_table_full'])} |")


if __name__ == "__main__":
    main()
