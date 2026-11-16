"""Flash crowds (docs/flash_prereg.md): measures of the 24 runs fc_T1B_F<k>_<method>_s<seed>, the pass
rule for FEVER (F1, F2) and the baselines beside it. Writes results/testbed_flash/runs.csv and report.md.

    python3 testbed/analyze_flash.py
"""
import csv
import glob
import os
from statistics import mean, stdev

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # RUNS, summary, num

OUT = os.path.join(os.path.dirname(SRC), "..", "results", "testbed_flash")
K = open(os.path.join(OUT, "selected_k.txt")).read().strip()
SEEDS = (4165, 4166, 4167)
METHODS = ["none", "ftmaster", "ftop", "ftodefender", "flora", "dms-btt-h1", "rdefender", FEVER]
LABEL = {"none": "No defense", "ftmaster": "FTMaster", "ftop": "FTOP", "ftodefender": "FTODefender",
         "flora": "FloRa", "dms-btt-h1": "DMS-BTT", "rdefender": "rDefender", FEVER: "FEVER"}
CAP = 3500
COLS = ["benign_harmed_pct", "benign_packet_in_lost_pct", "probe_post_success_pct", "hosts_blocked_benign",
        "ingress_drops", "sources_blocked_benign", "benign_deleted_per_min", "table_full", "s11_max",
        "s11_secs_ge90"]


def run_dir(m, s):
    """The counted run: its own folder, or a copy moved to _failed for wall time only (amendment 1)."""
    d = os.path.join(RUNS, f"fc_T1B_F{K}_{m}_s{s}")
    if os.path.exists(os.path.join(d, "summary.txt")):
        return d
    for f in sorted(glob.glob(os.path.join(RUNS, "_failed", f"fc_T1B_F{K}_{m}_s{s}.*")), reverse=True):
        log = os.path.join(f, "runner.log")
        if os.path.exists(log) and "artifacts in" in open(log).read() and os.path.exists(
                os.path.join(f, "controller_T1B.csv")):
            return f
    return None


def s11(d):
    with open(os.path.join(d, "switch_T1B_s11.csv")) as fh:
        n = [float(x["entries"]) for x in csv.DictReader(fh)]
    return max(n), float(sum(x >= 0.9 * CAP for x in n))


def blocks(d):
    """Host and ingress blocks: (time s, host, event)."""
    out = []
    with open(glob.glob(os.path.join(d, "controller_*_flows.csv"))[0]) as fh:
        for x in csv.DictReader(fh):
            if x["event"] in ("host_block", "ingress_drop"):
                out.append((float(x["t"]), x["src"], x["event"]))
    return out


rows, miss = [], []
for s in SEEDS:
    for m in METHODS:
        d = run_dir(m, s)
        if d is None:
            miss.append(f"{m} seed {s}")
            continue
        if not os.path.exists(os.path.join(d, "summary.txt")):
            os.system(f"python3 {os.path.dirname(SRC)}/summarize_run.py '{d}' > '{d}/summary.txt'")
        r = summary(d, window=False) or {}
        r["s11_max"], r["s11_secs_ge90"] = s11(d)
        for k in ("hosts_blocked_benign", "ingress_drops", "sources_blocked_benign", "table_full"):
            r[k] = float(r.get(k, 0) or 0)
        rows.append(dict(method=m, seed=s, dir=os.path.basename(d), **{k: r.get(k) for k in COLS},
                         blocks=blocks(d)))

with open(os.path.join(OUT, "runs.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["method", "seed", "run"] + COLS)
    for r in rows:
        w.writerow([r["method"], r["seed"], r["dir"]] + [r[k] for k in COLS])


def ms(m, k, d=2):
    x = [float(r[k]) for r in rows if r["method"] == m and num(r[k])]
    if not x:
        return "–"
    return f"{mean(x):.{d}f} ({stdev(x) if len(x) > 1 else 0:.{d}f})"


def total(m, k):
    return int(sum(float(r[k]) for r in rows if r["method"] == m and num(r[k])))


L = [f"# Flash crowds on T1B (F{K})", "",
     "docs/flash_prereg.md. 300 s runs, no attacker, three 12 s crowds per run, seeds 4165-4167. "
     "Mean (s.d.) over seeds; blocks are totals over the three runs.", ""]
sel = os.path.join(OUT, "selection.txt")
if os.path.exists(sel):
    L += ["Burst size (section 3): " + "; ".join(x.strip() for x in open(sel)) + f". Used: F{K}.", ""]
L += ["| Method | Harm % | Lost first packets % | New-connection success % | Benign hosts blocked | "
      "Benign sources blocked | Benign deletes/min | Table-Full | s11 largest poll | s11 s at >= 90 % |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for m in METHODS:
    L.append(f"| {LABEL[m]} | {ms(m, 'benign_harmed_pct', 3)} | {ms(m, 'benign_packet_in_lost_pct')} | "
             f"{ms(m, 'probe_post_success_pct', 1)} | {total(m, 'hosts_blocked_benign') + total(m, 'ingress_drops')} | "
             f"{total(m, 'sources_blocked_benign')} | {ms(m, 'benign_deleted_per_min')} | {ms(m, 'table_full', 0)} | "
             f"{ms(m, 's11_max', 0)} | {ms(m, 's11_secs_ge90', 0)} |")
fv = [r for r in rows if r["method"] == FEVER]
nb = sum(float(r["hosts_blocked_benign"]) + float(r["ingress_drops"]) for r in fv)
h_f = [float(r["benign_harmed_pct"]) for r in fv]
h_n = [float(r["benign_harmed_pct"]) for r in rows if r["method"] == "none"]
f1 = len(fv) == 3 and nb == 0
f2 = bool(h_f and h_n) and mean(h_f) <= mean(h_n) + 1.0
L += ["", "## Pass rule for FEVER (section 6)", "",
      f"- F1, no benign host blocked in any of FEVER's runs ({len(fv)} of 3 runs counted): "
      f"{'pass' if f1 else 'fail'} ({int(nb)} blocks)",
      f"- F2, FEVER's mean harm at most 1.0 point above no defense's: "
      + (f"{'pass' if f2 else 'fail'} ({mean(h_f):.3f} % against {mean(h_n):.3f} %)" if h_f and h_n else "not computable")]
for r in fv:
    for t, h, e in r["blocks"]:
        L.append(f"  - seed {r['seed']}: {e} of {h} at {t:.0f} s (controller time)")
if miss:
    L += ["", "Missing runs: " + ", ".join(miss)]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
