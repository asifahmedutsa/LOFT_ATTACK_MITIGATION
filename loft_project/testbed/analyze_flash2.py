"""Flash crowds, round 2 (docs/flash2_prereg.md): measures of the 48 runs
fc2_T1B_F<k>[H]_<method>_s<seed>, the controller-message drop share, the pass rule for FEVER (F1, F2)
for each placement, and which of FEVER's rules blocked the crowd host. Writes
results/testbed_flash2/runs.csv and report.md.

    python3 testbed/analyze_flash2.py
"""
import csv
import glob
import json
import os
import re
from statistics import mean, stdev

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # RUNS, summary, num, FEVER

HERE = os.path.dirname(SRC)
OUT = os.path.join(HERE, "..", "results", "testbed_flash2")
K = open(os.path.join(OUT, "selected_k.txt")).read().strip()
SEEDS = (4187, 4188, 4189)
PLACE = {f"F{K}": "spread", f"F{K}H": "one host"}
METHODS = ["none", "ftmaster", "ftop", "ftodefender", "flora", "dms-btt-h1", "rdefender", FEVER]
LABEL = {"none": "No defense", "ftmaster": "FTMaster", "ftop": "FTOP", "ftodefender": "FTODefender",
         "flora": "FloRa", "dms-btt-h1": "DMS-BTT", "rdefender": "rDefender", FEVER: "FEVER"}
CAP = 2000
CROWD_MAC = "00:00:00:00:01:03"          # d1h3, benign host 2 (testbed/traffic_driver.py CROWD_HOST)
VOL_X = json.load(open(os.path.join(HERE, "..", "results", "v21", "exported", "ens_config_fl_ll.json")))[
    "block"]["vol_x"]["T1B"]
COLS = ["benign_harmed_pct", "benign_packet_in_lost_pct", "probe_post_success_pct", "hosts_blocked_benign",
        "ingress_drops", "sources_blocked_benign", "benign_deleted_per_min", "table_full", "s11_max",
        "s11_secs_ge90", "s13_max", "drop_pct"]


def run_dir(v, m, s):
    """The counted run: its own folder, or a copy moved to _failed for wall time only (amendment 1)."""
    name = f"fc2_T1B_{v}_{m}_s{s}"
    d = os.path.join(RUNS, name)
    if os.path.exists(os.path.join(d, "summary.txt")):
        return d
    for f in sorted(glob.glob(os.path.join(RUNS, "_failed", name + ".*")), reverse=True):
        log = os.path.join(f, "runner.log")
        if os.path.exists(log) and "artifacts in" in open(log).read() and os.path.exists(
                os.path.join(f, "controller_T1B.csv")):
            return f
    return None


def entries(d, sw):
    with open(os.path.join(d, f"switch_T1B_{sw}.csv")) as fh:
        return [(float(x["t"]), float(x["entries"])) for x in csv.DictReader(fh)]


def drop_pct(d):
    """Share of the switches' controller messages that Open vSwitch dropped (rconn_overflow)."""
    def cov(f):
        out = {}
        for line in open(f):
            x = re.match(r"(\S+)\s+.*total:\s*(\d+)", line)
            if x:
                out[x.group(1)] = int(x.group(2))
        return out
    try:
        a, b = cov(os.path.join(d, "ovs_coverage_before.txt")), cov(os.path.join(d, "ovs_coverage_after.txt"))
    except FileNotFoundError:
        return None
    q = b.get("rconn_queued", 0) - a.get("rconn_queued", 0)
    o = b.get("rconn_overflow", 0) - a.get("rconn_overflow", 0)
    return 100.0 * o / (q + o) if q + o else 0.0


def blocks(d):
    """Host and ingress blocks: (time s, host, event, switch)."""
    out = []
    with open(glob.glob(os.path.join(d, "controller_*_flows.csv"))[0]) as fh:
        for x in csv.DictReader(fh):
            if x["event"] in ("host_block", "ingress_drop"):
                out.append((float(x["t"]), x["src"], x["event"], x["sw"]))
    return out


def crowds(d):
    """Start and end of each crowd (s, controller time), from the crowd flows in the truth files."""
    t0 = float(open(os.path.join(d, "controller_T1B_t0.txt")).read().split()[0])
    ts = []
    for f in glob.glob(os.path.join(d, "truth_d1h*.csv")):
        for r in csv.DictReader(open(f)):
            a = r["src"].split(".")
            if a[0] == "192" and int(a[1]) < 16:
                ts.append(float(r["t_first"]) - t0)
    ts.sort()
    out = []
    for t in ts:
        if out and t - out[-1][1] <= 5:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def rule(d, t, sw):
    """FEVER's rule for a host block, inferred from the blocking switch's poll at or before t: the
    volume rule if the table was >= 90 % full and the host held > X entries and >= 3x the median
    host's; otherwise the eviction rule."""
    polls = [p for p in entries(d, sw) if p[0] <= t + 1e-6]
    if not polls:
        return "eviction"
    tp, n = polls[-1]
    held = {}
    with open(os.path.join(d, f"switch_T1B_{sw}_macs.csv")) as fh:
        for x in csv.DictReader(fh):
            if abs(float(x["t"]) - tp) < 1e-6:
                held[x["mac"]] = int(x["entries"])
    h = sorted(v for v in held.values() if v > 0)
    med = h[len(h) // 2] if h else 0
    c = held.get(CROWD_MAC, 0)
    vol = n >= 0.9 * CAP and c > VOL_X[sw] and c >= 3 * max(med, 1)
    return f"{'volume' if vol else 'eviction'} (table {100 * n / CAP:.0f} %, d1h3 held {c}, median host {med})"


rows, miss = [], []
for s in SEEDS:
    for v in PLACE:
        for m in METHODS:
            d = run_dir(v, m, s)
            if d is None:
                miss.append(f"{PLACE[v]} {m} seed {s}")
                continue
            if not os.path.exists(os.path.join(d, "summary.txt")):
                os.system(f"python3 {HERE}/summarize_run.py '{d}' --capacity {CAP} > '{d}/summary.txt'")
            r = summary(d, window=False) or {}
            e11 = [n for _, n in entries(d, "s11")]
            r["s11_max"], r["s11_secs_ge90"] = max(e11), float(sum(n >= 0.9 * CAP for n in e11))
            r["s13_max"] = max(n for _, n in entries(d, "s13"))
            r["drop_pct"] = drop_pct(d)
            for k in ("hosts_blocked_benign", "ingress_drops", "sources_blocked_benign", "table_full"):
                r[k] = float(r.get(k, 0) or 0)
            rows.append(dict(placement=PLACE[v], method=m, seed=s, dir=d, **{k: r.get(k) for k in COLS},
                             blocks=blocks(d)))

with open(os.path.join(OUT, "runs.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["placement", "method", "seed", "run"] + COLS)
    for r in rows:
        w.writerow([r["placement"], r["method"], r["seed"], os.path.basename(r["dir"])] + [r[k] for k in COLS])


def sel(p, m):
    return [r for r in rows if r["placement"] == p and r["method"] == m]


def ms(p, m, k, d=2):
    x = [float(r[k]) for r in sel(p, m) if num(r[k])]
    if not x:
        return "–"
    return f"{mean(x):.{d}f} ({stdev(x) if len(x) > 1 else 0:.{d}f})"


def total(p, m, k):
    return int(sum(float(r[k]) for r in sel(p, m) if num(r[k])))


L = [f"# Flash crowds on T1B, round 2 (F{K}, tables of {CAP:,} entries)", "",
     "docs/flash2_prereg.md. 300 s runs, no attacker, three 12 s crowds per run, seeds 4187-4189. "
     "Mean (s.d.) over seeds; blocks are totals over the three runs.", ""]
f = os.path.join(OUT, "selection.txt")
if os.path.exists(f):
    L += ["Crowd rate (section 3): " + "; ".join(x.strip() for x in open(f)) + f". Used: F{K}.", ""]
for p in ("spread", "one host"):
    L += [f"## {p.capitalize()}", "",
          "| Method | Harm % | Lost first packets % | New-connection success % | Benign hosts blocked | "
          "Benign sources blocked | Benign deletes/min | Table-Full | s11 largest poll | s11 s at >= 90 % | "
          "s13 largest poll | Controller messages dropped % |", "|" + "---|" * 12]
    for m in METHODS:
        L.append(f"| {LABEL[m]} | {ms(p, m, 'benign_harmed_pct', 3)} | {ms(p, m, 'benign_packet_in_lost_pct')} | "
                 f"{ms(p, m, 'probe_post_success_pct', 1)} | "
                 f"{total(p, m, 'hosts_blocked_benign') + total(p, m, 'ingress_drops')} | "
                 f"{total(p, m, 'sources_blocked_benign')} | {ms(p, m, 'benign_deleted_per_min')} | "
                 f"{ms(p, m, 'table_full', 0)} | {ms(p, m, 's11_max', 0)} | {ms(p, m, 's11_secs_ge90', 0)} | "
                 f"{ms(p, m, 's13_max', 0)} | {ms(p, m, 'drop_pct', 1)} |")
    fv, nd = sel(p, FEVER), sel(p, "none")
    nb = sum(float(r["hosts_blocked_benign"]) + float(r["ingress_drops"]) for r in fv)
    h_f = [float(r["benign_harmed_pct"]) for r in fv]
    h_n = [float(r["benign_harmed_pct"]) for r in nd]
    f1 = len(fv) == 3 and nb == 0
    f2 = bool(h_f and h_n) and mean(h_f) <= mean(h_n) + 1.0
    L += ["", f"Pass rule for FEVER, {p} (section 6):", "",
          f"- F1, no benign host blocked in any of FEVER's runs ({len(fv)} of 3 runs counted): "
          f"{'pass' if f1 else 'fail'} ({int(nb)} blocks)",
          f"- F2, FEVER's mean harm at most 1.0 point above no defense's: "
          + (f"{'pass' if f2 else 'fail'} ({mean(h_f):.3f} % against {mean(h_n):.3f} %)" if h_f and h_n
             else "not computable")]
    for r in fv:
        cw = crowds(r["dir"])
        for t, h, e, sw in r["blocks"]:
            where = next((f"crowd {i + 1} ({a:.0f}-{b:.0f} s), {t - a:.0f} s after its start"
                          for i, (a, b) in enumerate(cw) if a <= t <= b + 15), "outside the crowds")
            how = f", {rule(r['dir'], t, sw)}" if e == "host_block" and h == CROWD_MAC else ""
            L.append(f"  - seed {r['seed']}: {e} of {h} on {sw} at {t:.0f} s, {where}{how}")
    L.append("")

# Round 1 beside it: the controller-message drop share of its runs (3,500 entries, F8).
r1 = sorted(glob.glob(os.path.join(RUNS, "fc_T1B_F8_*_s416[5-7]")))
dp = [x for x in (drop_pct(d) for d in r1) if x is not None]
if dp:
    L += [f"Round 1 (3,500 entries, F8, {len(dp)} runs): controller messages dropped {min(dp):.1f} % to "
          f"{max(dp):.1f} % (mean {mean(dp):.1f} %).", ""]
if miss:
    L += ["Missing runs: " + ", ".join(miss)]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
