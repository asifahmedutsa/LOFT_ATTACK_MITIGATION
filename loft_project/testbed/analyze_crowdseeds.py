"""One-host flash crowd on more seeds (docs/crowdseeds_prereg.md): measures of the 20 runs
fc3_T1B_F2H_<method>_s<seed> as in round 2, C1 (how often FEVER blocked the crowd host, with an exact
95 % interval, alone and pooled with round 2), C2 (harm against no defense, per seed) and C3 (s11's
largest poll in the first crowd, FEVER's runs with and without a block). Writes
results/testbed_crowdseeds/runs.csv and report.md.

    python3 testbed/analyze_crowdseeds.py
"""
import csv
import glob
import json
import os
import re
from statistics import mean, stdev

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # RUNS, summary, num, FEVER
exec(compile(_code[_code.index("\ndef suspended"):_code.index("\ndef collect")], SRC, "exec"))   # rescuable
F2 = os.path.join(HERE, "analyze_flash2.py")
_code = open(F2).read()
CAP = 2000
CROWD_MAC = "00:00:00:00:01:03"          # d1h3 (testbed/traffic_driver.py CROWD_HOST)
VOL_X = json.load(open(os.path.join(HERE, "..", "results", "v21", "exported", "ens_config_fl_ll.json")))[
    "block"]["vol_x"]["T1B"]
exec(compile(_code[_code.index("\ndef entries"):_code.index("\nrows, miss")], F2, "exec"))  # round 2's measures

RES = os.path.join(HERE, "..", "results")
OUT = os.path.join(RES, "testbed_crowdseeds")
K = open(os.path.join(RES, "testbed_flash2", "selected_k.txt")).read().strip()
V = f"F{K}H"
SEEDS = tuple(range(4200, 4210))
METHODS = ["none", FEVER]
LABEL = {"none": "No defense", FEVER: "FEVER"}
COLS = ["benign_harmed_pct", "benign_packet_in_lost_pct", "probe_post_success_pct", "hosts_blocked_benign",
        "benign_deleted_per_min", "s11_max", "s11_secs_ge90", "s13_max", "drop_pct", "s11_max_crowd1"]


def run_dir(m, s, tag="fc3"):
    """The counted run under the campaign's validity rule as changed by amendment 1."""
    n = f"{tag}_T1B_{V}_{m}_s{s}"
    d = os.path.join(RUNS, n)
    if os.path.exists(os.path.join(d, "summary.txt")):
        return d
    for c in sorted(glob.glob(os.path.join(RUNS, "_failed", n + ".*"))):
        if rescuable(c, 300):                # rescuable() summarizes at 3,500 entries
            os.system(f"python3 {HERE}/summarize_run.py '{c}' --capacity {CAP} > '{c}/summary.txt'")
            return c
    return None


def measure(d):
    r = summary(d, window=False) or {}
    e11 = entries(d, "s11")
    r["s11_max"] = max(n for _, n in e11)
    r["s11_secs_ge90"] = float(sum(n >= 0.9 * CAP for _, n in e11))
    r["s13_max"] = max(n for _, n in entries(d, "s13"))
    r["drop_pct"] = drop_pct(d)
    r["hosts_blocked_benign"] = float(r.get("hosts_blocked_benign", 0) or 0)
    cw = crowds(d)
    r["s11_max_crowd1"] = max((n for t, n in e11 if cw and cw[0][0] <= t <= cw[0][1]), default=None)
    b = blocks(d)
    return r, b, cw


def binom_cdf(k, n, p):
    from math import comb
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k, n):
    """Exact 95 % interval for k successes in n, by bisection on the binomial tail."""
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    low = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) < 0.025)
    high = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > 0.025)
    return low, high


rows, miss = [], []
for s in SEEDS:
    for m in METHODS:
        d = run_dir(m, s)
        if d is None:
            miss.append(f"{LABEL[m]} seed {s}")
            continue
        r, b, cw = measure(d)
        rows.append(dict(method=m, seed=s, dir=d, blocks=b, crowds=cw,
                         crowd_block=[x for x in b if x[2] == "host_block" and x[1] == CROWD_MAC],
                         **{k: r.get(k) for k in COLS}))

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "runs.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["method", "seed", "run"] + COLS + ["crowd_host_blocked"])
    for r in rows:
        w.writerow([r["method"], r["seed"], os.path.basename(r["dir"])] + [r[k] for k in COLS]
                   + [int(bool(r["crowd_block"]))])

# Round 2's FEVER runs on the one-host crowd, for the pooled rate and beside C3.
r2 = []
for s in (4187, 4188, 4189):
    d = run_dir(FEVER, s, tag="fc2")
    if d is not None:
        _, b, cw = measure(d)
        r2.append(dict(seed=s, dir=d, crowd_block=[x for x in b if x[2] == "host_block" and x[1] == CROWD_MAC],
                       s11_max_crowd1=max((n for t, n in entries(d, "s11") if cw and cw[0][0] <= t <= cw[0][1]),
                                          default=None)))


def sel(m):
    return [r for r in rows if r["method"] == m]


def ms(m, k, d=2):
    x = [float(r[k]) for r in sel(m) if num(r[k])]
    if not x:
        return "–"
    return f"{mean(x):.{d}f} ({stdev(x) if len(x) > 1 else 0:.{d}f})"


fv, nd = sel(FEVER), sel("none")
L = [f"# One-host flash crowd on more seeds (F{K}H, tables of {CAP:,} entries)", "",
     "docs/crowdseeds_prereg.md. 300 s runs, no attacker, three 12 s crowds from d1h3, seeds 4200-4209. "
     "Mean (s.d.) over seeds.", "",
     "| Method | Runs | Harm % | Lost first packets % | New-connection success % | Runs with d1h3 blocked | "
     "Benign deletes/min | s11 largest poll | s11 s at >= 90 % | s13 largest poll | "
     "Controller messages dropped % |", "|" + "---|" * 11]
for m in METHODS:
    L.append(f"| {LABEL[m]} | {len(sel(m))} | {ms(m, 'benign_harmed_pct', 3)} | "
             f"{ms(m, 'benign_packet_in_lost_pct')} | {ms(m, 'probe_post_success_pct', 1)} | "
             f"{sum(bool(r['crowd_block']) for r in sel(m))} | {ms(m, 'benign_deleted_per_min')} | "
             f"{ms(m, 's11_max', 0)} | {ms(m, 's11_secs_ge90', 0)} | {ms(m, 's13_max', 0)} | "
             f"{ms(m, 'drop_pct', 1)} |")

k, n = sum(bool(r["crowd_block"]) for r in fv), len(fv)
k2, n2 = sum(bool(r["crowd_block"]) for r in r2), len(r2)
L += ["", "## C1: how often FEVER blocked the crowd host", ""]
if n:
    lo, hi = clopper_pearson(k, n)
    L.append(f"- This study: {k} of {n} runs (95 % interval {100 * lo:.0f} % to {100 * hi:.0f} %).")
    lo, hi = clopper_pearson(k + k2, n + n2)
    L.append(f"- Pooled with round 2 ({k2} of {n2}): {k + k2} of {n + n2} runs "
             f"(95 % interval {100 * lo:.0f} % to {100 * hi:.0f} %).")

L += ["", "## C2: harm against no defense (reported, not tested)", "",
      "| Seed | No defense harm % | FEVER harm % | Difference (points) | d1h3 blocked |", "|---|---|---|---|---|"]
hn = {r["seed"]: float(r["benign_harmed_pct"]) for r in nd if num(r["benign_harmed_pct"])}
diffs = []
for r in fv:
    if not num(r["benign_harmed_pct"]) or r["seed"] not in hn:
        continue
    h = float(r["benign_harmed_pct"])
    diffs.append(h - hn[r["seed"]])
    L.append(f"| {r['seed']} | {hn[r['seed']]:.3f} | {h:.3f} | {diffs[-1]:+.3f} | "
             f"{'yes' if r['crowd_block'] else 'no'} |")
if diffs:
    L += ["", f"Mean paired difference {mean(diffs):+.3f} points over {len(diffs)} seeds."]

L += ["", "## C3: s11's largest poll in the first crowd", ""]
bl = [r["s11_max_crowd1"] for r in fv if r["crowd_block"] and r["s11_max_crowd1"] is not None]
un = [r["s11_max_crowd1"] for r in fv if not r["crowd_block"] and r["s11_max_crowd1"] is not None]
L.append(f"- FEVER runs with d1h3 blocked: {', '.join(f'{x:.0f}' for x in sorted(bl)) or 'none'}")
L.append(f"- FEVER runs without a block: {', '.join(f'{x:.0f}' for x in sorted(un)) or 'none'}")
if not bl or not un:
    L.append("- C3 cannot be checked: FEVER blocked d1h3 in all runs or in none.")
else:
    L.append(f"- Every unblocked run peaks lower than every blocked run: "
             f"{'yes, the seed-4188 reading is supported' if max(un) < min(bl) else 'no, the seed-4188 reading is not supported'}.")
L.append("- Round 2, for comparison: " + "; ".join(
    f"seed {r['seed']} {r['s11_max_crowd1']:.0f} ({'blocked' if r['crowd_block'] else 'not blocked'})"
    for r in r2 if r["s11_max_crowd1"] is not None) + ".")

L += ["", "## Blocks of d1h3 by FEVER", ""]
for r in fv:
    for t, h, e, sw in r["crowd_block"]:
        where = next((f"crowd {i + 1} ({a:.0f}-{b:.0f} s), {t - a:.0f} s after its start"
                      for i, (a, b) in enumerate(r["crowds"]) if a <= t <= b + 15), "outside the crowds")
        L.append(f"- seed {r['seed']}: on {sw} at {t:.0f} s, {where}, {rule(r['dir'], t, sw)}")
other = [(r["seed"], x) for r in rows for x in r["blocks"] if x[2] == "host_block" and x[1] != CROWD_MAC]
L += [f"- Blocks of any other benign host: {len(other)}"]
if miss:
    L += ["", "Missing runs: " + ", ".join(miss)]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
