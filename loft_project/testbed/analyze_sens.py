"""Sensitivity of FEVER to its fixed settings (docs/sensitivity_prereg.md): measures of the 90 runs
sens_T1B_<variant>_<method>_s<seed>, paired with default FEVER's runs (the final campaign's runs.csv
for the attacks and benign only, round 2's runs.csv for the one-host crowd), and the pass rules R1, R2
and the report R3. Writes results/testbed_sens/runs.csv and report.md.

    python3 testbed/analyze_sens.py
"""
import csv
import glob
import json
import os
from statistics import mean

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # RUNS, summary, num, OCC, FEVER
exec(compile(_code[_code.index("\ndef suspended"):_code.index("\ndef collect")], SRC, "exec"))   # first_valid

HERE = os.path.dirname(SRC)
RES = os.path.join(HERE, "..", "results")
OUT = os.path.join(RES, "testbed_sens")
SETS = {"fever-s-r60": "rho 0.6", "fever-s-r80": "rho 0.8", "fever-s-k2": "k 2", "fever-s-k4": "k 4",
        "fever-s-v125": "volume x1.25", "fever-s-v200": "volume x2.0"}
ATT = {"A2": "G2", "A4": "Mimic", "E9P": "Aware"}
SEEDS = (4160, 4161, 4162)
CSEEDS = (4187, 4188, 4189)
CAP_C = 2000
CROWD_MAC = "00:00:00:00:01:03"          # d1h3 (testbed/traffic_driver.py CROWD_HOST)
EC = json.load(open(os.path.join(RES, "v21", "exported", "ens_config_fl_ll.json")))
VOL_X = EC["block"]["vol_x"]["T1B"]
COLS = ["benign_harmed_pct", OCC, "probe_post_success_pct", "first_attack_block_s", "hosts_blocked_benign"]


def run_dir(v, m, s):
    """The counted run under the campaign's validity rule as changed by amendment 1."""
    n = f"sens_T1B_{v}_{m}_s{s}"
    d = os.path.join(RUNS, n)
    if os.path.exists(os.path.join(d, "summary.txt")):
        return d
    for c in sorted(glob.glob(os.path.join(RUNS, "_failed", n + ".*"))):
        if rescuable(c, 300):
            if v == "F2H":                   # rescuable() summarizes at 3,500 entries
                os.system(f"python3 {HERE}/summarize_run.py '{c}' --capacity {CAP_C} > '{c}/summary.txt'")
            return c
    return None


def blocks(d):
    """Host and ingress blocks: (time s, host, event, switch)."""
    out = []
    with open(glob.glob(os.path.join(d, "controller_*_flows.csv"))[0]) as fh:
        for x in csv.DictReader(fh):
            if x["event"] in ("host_block", "ingress_drop"):
                out.append((float(x["t"]), x["src"], x["event"], x["sw"]))
    return out


def rule(d, t, sw, m):
    """The rule of a block of the crowd host, from the blocking switch's poll at or before t: the volume
    rule if the table was >= 90 % full and the host held > X (this setting's) and >= 3x the median host's
    entries; otherwise the eviction rule."""
    x = VOL_X[sw] / 1.5 * {"fever-s-v125": 1.25, "fever-s-v200": 2.0}.get(m, 1.5)
    with open(os.path.join(d, f"switch_T1B_{sw}.csv")) as fh:
        polls = [(float(p["t"]), float(p["entries"])) for p in csv.DictReader(fh) if float(p["t"]) <= t + 1e-6]
    if not polls:
        return "eviction"
    tp, n = polls[-1]
    held = {}
    with open(os.path.join(d, f"switch_T1B_{sw}_macs.csv")) as fh:
        for p in csv.DictReader(fh):
            if abs(float(p["t"]) - tp) < 1e-6:
                held[p["mac"]] = int(p["entries"])
    h = sorted(v for v in held.values() if v > 0)
    med = h[len(h) // 2] if h else 0
    c = held.get(CROWD_MAC, 0)
    vol = n >= 0.9 * CAP_C and c > x and c >= 3 * max(med, 1)
    return f"{'volume' if vol else 'eviction'} (table {100 * n / CAP_C:.0f} %, d1h3 held {c}, median {med})"


# Default FEVER, as reported in the source studies.
base = {}
with open(os.path.join(RES, "testbed_prereg_final", "runs.csv")) as fh:
    for r in csv.DictReader(fh):
        if r["length"] == "300 s" and r["trace"] == "T1B" and r["method"] == FEVER:
            base[(r["traffic"], int(r["seed"]))] = r
crowd_base = {}
with open(os.path.join(RES, "testbed_flash2", "runs.csv")) as fh:
    for r in csv.DictReader(fh):
        if r["placement"] == "one host":
            crowd_base[(r["method"], int(r["seed"]))] = r

rows, miss = [], []
for m in SETS:
    for v, seeds in [(a, SEEDS) for a in (*ATT, "benign")] + [("F2H", CSEEDS)]:
        for s in seeds:
            d = run_dir(v, m, s)
            if d is None:
                miss.append(f"{SETS[m]} {v} seed {s}")
                continue
            r = summary(d, window=v != "F2H") or {}
            b = blocks(d)
            rows.append(dict(method=m, traffic=v, seed=s, dir=d, blocks=b,
                             crowd_block=[x for x in b if x[2] == "host_block" and x[1] == CROWD_MAC],
                             **{k: r.get(k) for k in COLS}))

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "runs.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["method", "traffic", "seed", "run"] + COLS + ["host_blocks"])
    for r in rows:
        w.writerow([r["method"], r["traffic"], r["seed"], os.path.basename(r["dir"])] + [r[k] for k in COLS]
                   + [sum(x[2] == "host_block" for x in r["blocks"])])


def mv(xs):
    """Mean of the numbers among xs; the source studies' runs.csv give them as text."""
    out = []
    for x in xs:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            pass
    return mean(out) if out else None


def f(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


def sel(m, v):
    return [r for r in rows if r["method"] == m and r["traffic"] == v]


L = ["# Sensitivity of FEVER to its fixed settings (T1B)", "",
     "docs/sensitivity_prereg.md. One setting changed at a time; default FEVER's runs from "
     "results/testbed_prereg_final (attacks, benign only) and results/testbed_flash2 (one-host crowd). "
     "Means over three seeds.", "",
     "## R1: attacks (harm at most 0.5 point and occupancy at most 5 points above default FEVER)", "",
     "| Setting | Attack | Harm % | Default | Occupancy % | Default | New-connection success % | Default | "
     "First block s | Default | Result |", "|" + "---|" * 11]
r1 = []
for m in SETS:
    for v, nm in ATT.items():
        rs = sel(m, v)
        bs = [base[(v, r["seed"])] for r in rs if (v, r["seed"]) in base]
        h, hb = mv(r["benign_harmed_pct"] for r in rs), mv(b["benign_harmed_pct"] for b in bs)
        o, ob = mv(r[OCC] for r in rs), mv(b[OCC] for b in bs)
        ok = len(rs) == 3 and len(bs) == 3 and None not in (h, hb, o, ob) and h <= hb + 0.5 and o <= ob + 5.0
        r1.append(ok)
        L.append(f"| {SETS[m]} | {nm} | {f(h, 3)} | {f(hb, 3)} | {f(o)} | {f(ob)} | "
                 f"{f(mv(r['probe_post_success_pct'] for r in rs), 1)} | "
                 f"{f(mv(b['probe_post_success_pct'] for b in bs), 1)} | "
                 f"{f(mv(r['first_attack_block_s'] for r in rs), 0)} | "
                 f"{f(mv(b['first_attack_block_s'] for b in bs), 0)} | {'pass' if ok else 'fail'} |")
L += ["", f"R1: {sum(r1)} of {len(r1)} setting-attack pairs pass.", "",
      "## R2: no attack (no benign host blocked)", "",
      "| Setting | Runs counted | Benign host blocks | Harm % | Default harm % | Result |", "|---|---|---|---|---|---|"]
r2 = []
for m in SETS:
    rs = sel(m, "benign")
    nb = sum(x[2] == "host_block" for r in rs for x in r["blocks"])
    ok = len(rs) == 3 and nb == 0
    r2.append(ok)
    L.append(f"| {SETS[m]} | {len(rs)} | {nb} | {f(mv(r['benign_harmed_pct'] for r in rs), 3)} | "
             f"{f(mv(base[('benign', s)]['benign_harmed_pct'] for s in SEEDS if ('benign', s) in base), 3)} | "
             f"{'pass' if ok else 'fail'} |")
L += ["", f"R2: {sum(r2)} of {len(r2)} settings pass.", "",
      "## R3: one-host crowd (F2H, capacity 2,000; reported, not tested)", "",
      "| Setting | Runs counted | Runs with the crowd host blocked | Harm % | No defense harm % | Result |",
      "|---|---|---|---|---|---|"]
hn = mv(crowd_base[("none", s)]["benign_harmed_pct"] for s in CSEEDS if ("none", s) in crowd_base)
fb = [s for s in CSEEDS if (FEVER, s) in crowd_base and float(crowd_base[(FEVER, s)]["hosts_blocked_benign"]) > 0]
L.append(f"| Default (round 2) | 3 | {len(fb)} | "
         f"{f(mv(crowd_base[(FEVER, s)]['benign_harmed_pct'] for s in CSEEDS if (FEVER, s) in crowd_base), 3)} | "
         f"{f(hn, 3)} | – |")
notes = []
for m in SETS:
    rs = sel(m, "F2H")
    nb = sum(bool(r["crowd_block"]) for r in rs)
    L.append(f"| {SETS[m]} | {len(rs)} | {nb} | {f(mv(r['benign_harmed_pct'] for r in rs), 3)} | {f(hn, 3)} | "
             f"{'avoids the crowd block' if len(rs) == 3 and nb == 0 else 'does not avoid it'} |")
    for r in rs:
        for t, h, e, sw in r["crowd_block"]:
            notes.append(f"- {SETS[m]}, seed {r['seed']}: d1h3 blocked on {sw} at {t:.0f} s, "
                         f"{rule(r['dir'], t, sw, m)}")
L += [""] + notes
if miss:
    L += ["", "Missing runs: " + ", ".join(miss)]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
