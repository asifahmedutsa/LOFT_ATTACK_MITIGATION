"""Local vs federated detector on Mininet/Ryu (testbed/matrix_fl.sh) against the simulator.

  python3 testbed/compare_fl.py [--runs ~/loft-runs] [--out results/testbed_fl]

Simulator reference: results/testbed_fl/sim_reference.csv (testbed/fl_sim_reference.py), the
same cells on seed 4000 and the mean and range over seeds 8000-8009.
Writes table_fl.csv and prints a Markdown table.
"""
import argparse
import csv
import os

from compare_matrix import summary

MODEL = {"local": "local", "v21": "federated"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=os.path.expanduser("~/loft-runs"))
    ap.add_argument("--out", default="results/testbed_fl")
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ref = {}
    for r in csv.DictReader(open(os.path.join(root, "results/testbed_fl/sim_reference.csv"))):
        ref.setdefault((r["model"], r["domain"], r["variant"]), {})[int(r["seed"])] = float(r["harmed"])
    rows = []
    for cell in ("D1 A2", "D1 A3", "D1 A6", "D2 A1", "D2 A3", "D2 A6", "D3 A1", "D3 A2", "D3 A6"):
        d, v = cell.split()
        for m in ("local", "v21"):
            p = os.path.join(a.runs, f"fl_{d}_{v}_{m}_s4000", "summary.txt")
            if not os.path.exists(p):
                continue
            s = summary(p)
            sim = ref.get((MODEL[m], d, v), {})
            many = [x for k, x in sim.items() if k != 4000]
            rows.append(dict(domain=d, variant=v, model=MODEL[m], tb_harmed=s.get("benign_harmed_pct"),
                             sim_s4000=round(sim[4000], 2) if 4000 in sim else "",
                             sim_mean=round(sum(many) / len(many), 2) if many else "",
                             sim_min=round(min(many), 2) if many else "",
                             sim_max=round(max(many), 2) if many else "",
                             tb_packet_in_lost=s.get("benign_packet_in_lost_pct"),
                             tb_table_full=s.get("table_full")))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "table_fl.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("| Controller | Attack | Model | Testbed harmed % | Sim seed 4000 | Sim mean [min, max] | "
          "Packet-In lost % |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['domain']} | {r['variant']} | {r['model']} | {r['tb_harmed']} | {r['sim_s4000']} | "
              f"{r['sim_mean']} [{r['sim_min']}, {r['sim_max']}] | {r['tb_packet_in_lost']} |")


if __name__ == "__main__":
    main()
