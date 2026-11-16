"""More colluding attackers (docs/scale_prereg.md): measures of the runs sc<n>_T1B_<attack>_<method>_s<seed>,
the tests S1-S3, and the campaign's two-attacker runs beside them. Writes results/testbed_scale/runs.csv
and report.md.

    python3 testbed/analyze_scale.py
"""
import csv
import glob
import os
from math import comb
from statistics import mean, stdev

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # RUNS, summary, traffic_window, num

HERE = os.path.dirname(SRC)
OUT = os.path.join(HERE, "..", "results", "testbed_scale")
CAMP = os.path.join(HERE, "..", "results", "testbed_prereg_final", "runs.csv")
SEEDS = (4184, 4185, 4186)
NS = (4, 8)
ATTS = ("A2", "EVX")
BASE = ["ftmaster", "ftodefender", "dms-btt-h1"]
METHODS = ["none", FEVER] + BASE
LABEL = {"none": "No defense", FEVER: "FEVER", "ftmaster": "FTMaster", "ftodefender": "FTODefender",
         "dms-btt-h1": "DMS-BTT"}
ANAME = {"A2": "G2", "EVX": "EVX"}
CAP = 3500


def is_attacker(mac):
    try:
        return 5 <= int(mac[-2:], 16) < 0x64
    except ValueError:
        return False


def run_dir(n, v, m, s):
    """The counted run: its own folder, or a copy moved to _failed for wall time only (amendment 1)."""
    name = f"sc{n}_T1B_{v}_{m}_s{s}"
    d = os.path.join(RUNS, name)
    if os.path.exists(os.path.join(d, "summary.txt")):
        return d
    for f in sorted(glob.glob(os.path.join(RUNS, "_failed", name + ".*")), reverse=True):
        log = os.path.join(f, "runner.log")
        if os.path.exists(log) and "artifacts in" in open(log).read() and os.path.exists(
                os.path.join(f, "controller_T1B.csv")):
            if not os.path.exists(os.path.join(f, "summary.txt")):
                os.system(f"python3 {HERE}/summarize_run.py '{f}' > '{f}/summary.txt'")
            return f
    return None


def occupancy(d, end, start=50.0):
    """Attack share of each switch's table (all attacker hosts), mean over the polls of the traffic
    window, then over the three switches (%), as analyze_final.occupancy_window for two attackers."""
    out = []
    for sl in sorted(glob.glob(os.path.join(d, "switch_T1B_s1?.csv"))):
        pa = {}
        with open(sl.replace(".csv", "_macs.csv")) as f:
            for x in csv.DictReader(f):
                if is_attacker(x["mac"]):
                    pa[float(x["t"])] = pa.get(float(x["t"]), 0) + int(x["entries"])
        with open(sl) as f:
            ts = [float(x["t"]) for x in csv.DictReader(f)]
        p = [pa.get(t, 0) / CAP for t in ts if start <= t <= end]
        out.append(100 * mean(p) if p else None)
    return mean(out) if out and None not in out else None


def blocks(d):
    att, ben = {}, {}
    with open(glob.glob(os.path.join(d, "controller_*_flows.csv"))[0]) as fh:
        for x in csv.DictReader(fh):
            if x["event"] == "host_block":
                (att if is_attacker(x["src"]) else ben).setdefault(x["src"], float(x["t"]))
    return att, ben


rows, miss = [], []
for s in SEEDS:
    for n in NS:
        for v in ATTS:
            for m in METHODS:
                if m == "none" and n != 8:
                    continue
                d = run_dir(n, v, m, s)
                if d is None:
                    miss.append(f"n={n} {ANAME[v]} {m} seed {s}")
                    continue
                r = summary(d, window=False) or {}
                w = traffic_window(d, 300)
                att, ben = blocks(d)
                rows.append(dict(n=n, traffic=v, method=m, seed=s, run=os.path.basename(d),
                                 occupancy=occupancy(d, w[1]) if w else None,
                                 benign_harmed_pct=r.get("benign_harmed_pct"),
                                 probe_post_success_pct=r.get("probe_post_success_pct"),
                                 benign_packet_in_lost_pct=r.get("benign_packet_in_lost_pct"),
                                 attackers_blocked=len(att), benign_blocked=len(ben),
                                 first_block_s=round(min(att.values()) - 50, 1) if att else None,
                                 last_block_s=round(max(att.values()) - 50, 1) if len(att) == n else None,
                                 decision_ms_mean=r.get("decision_ms_mean"), ctrl_cpu_pct=r.get("ctrl_cpu_pct")))
os.makedirs(OUT, exist_ok=True)
COLS = list(rows[0]) if rows else []
with open(os.path.join(OUT, "runs.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, COLS)
    w.writeheader()
    w.writerows(rows)

camp = [x for x in csv.DictReader(open(CAMP)) if x["length"] == "300 s" and x["trace"] == "T1B"]


def ms(v, m, k, n, d=2):
    if n == 2:
        x = [float(r[k]) for r in camp if r["traffic"] == v and r["method"] == m and num(r.get(k))]
    else:
        x = [float(r[k]) for r in rows if r["n"] == n and r["traffic"] == v and r["method"] == m and num(r[k])]
    if not x:
        return "–"
    return f"{mean(x):.{d}f} ({stdev(x) if len(x) > 1 else 0:.{d}f})"


def blocked(v, m, n):
    x = [r for r in rows if r["n"] == n and r["traffic"] == v and r["method"] == m]
    return f"{sum(r['attackers_blocked'] for r in x)} of {n * len(x)}" if x else "–"


L = ["# More colluding attackers on T1B", "",
     "docs/scale_prereg.md. Mean (s.d.) over seeds; n = 2 is the final campaign (seeds 4160-4164).", ""]
for v in ATTS:
    L += [f"## {ANAME[v]}", "",
          "| Method | n | Occupancy % | Harm % | New-connection success % | Lost first packets % | "
          "Attackers blocked | Benign hosts blocked |", "|---|---|---|---|---|---|---|---|"]
    for m in METHODS:
        for n in (2,) + NS:
            if m == "none" and n == 4:
                continue
            ben = "–" if n == 2 else str(sum(r["benign_blocked"] for r in rows
                                              if r["n"] == n and r["traffic"] == v and r["method"] == m))
            L.append(f"| {LABEL[m]} | {n} | {ms(v, m, 'occupancy', n)} | {ms(v, m, 'benign_harmed_pct', n, 3)} | "
                     f"{ms(v, m, 'probe_post_success_pct', n, 1)} | {ms(v, m, 'benign_packet_in_lost_pct', n)} | "
                     f"{'–' if n == 2 else blocked(v, m, n)} | {ben} |")
    L.append("")

# S1: G2, FEVER's occupancy below each baseline's, pairs over n = 4 and 8.
res = []
for b in BASE:
    wins = tot = 0
    for n in NS:
        for s in SEEDS:
            f = [r["occupancy"] for r in rows if (r["n"], r["traffic"], r["method"], r["seed"]) == (n, "A2", FEVER, s)]
            c = [r["occupancy"] for r in rows if (r["n"], r["traffic"], r["method"], r["seed"]) == (n, "A2", b, s)]
            if f and c and None not in (f[0], c[0]):
                tot += 1
                wins += f[0] < c[0]
    p = sum(comb(tot, k) for k in range(wins, tot + 1)) / 2 ** tot if tot else 1.0
    res.append([b, wins, tot, p])
order = sorted(range(len(res)), key=lambda i: res[i][3])
adj, run_max = [0.0] * len(res), 0.0
for rank, i in enumerate(order):
    run_max = max(run_max, min(1.0, (len(res) - rank) * res[i][3]))
    adj[i] = run_max
L += ["## Tests", "", "| S1 (G2): FEVER below | Wins / pairs | p | p (Holm) | Supported |", "|---|---|---|---|---|"]
for (b, wins, tot, p), pa in zip(res, adj):
    L.append(f"| {LABEL[b]} | {wins} / {tot} | {p:.4f} | {pa:.4f} | {'yes' if pa < 0.05 and tot == 6 else 'no'} |")
nb = sum(r["benign_blocked"] for r in rows if r["method"] == FEVER)
L += ["", f"- S2 (EVX): reported above; FEVER blocked {sum(r['attackers_blocked'] for r in rows if r['method'] == FEVER and r['traffic'] == 'EVX')} "
      f"EVX attackers over its {sum(1 for r in rows if r['method'] == FEVER and r['traffic'] == 'EVX')} EVX runs.",
      f"- S3: FEVER blocked {nb} benign hosts over its {sum(1 for r in rows if r['method'] == FEVER)} runs: "
      f"{'pass' if nb == 0 else 'fail'}."]
if miss:
    L += ["", "Missing runs: " + ", ".join(miss)]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
