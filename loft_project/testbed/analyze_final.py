"""Preregistered analysis of the final testbed campaign (docs/final_campaign_prereg.md, sections 5-8).
Written before any run on seeds 4160-4164; hashed with the preregistration.

H1-H6: one-sided exact sign tests over paired runs (same trace, attack and seed), a tie counts against
FEVER, Holm over all 33 tests together, alpha 0.05. A hypothesis is supported only if its test passes
and no single attack contradicts it (FEVER's mean over that attack's seeds is not worse than the
comparator's by more than 0.1 point of harm, 2 points of occupancy or 5 points of probe success).
H7 and section 8 are reported, not tested. A missing run drops its pairs, which are counted.

    python3 testbed/analyze_final.py      # writes results/testbed_prereg_final/{runs.csv, tests.csv, report.md}

FIN_RUNS, FIN_TAG and FIN_OUT override the run directory, the run-name prefix and the output (for a
dry run on renamed development summaries; never for the campaign).
"""
import csv
import os
import random
import re
from math import comb
from statistics import mean

RUNS = os.path.expanduser(os.environ.get("FIN_RUNS", "~/loft-runs"))
TAG = os.environ.get("FIN_TAG", "fin")
OUT = os.environ.get("FIN_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                                              "testbed_prereg_final"))
FEVER = "fever-fl-ll"
SIX = ["ftmaster", "ftop", "ftodefender", "flora", "dms-btt", "rdefender"]
POOLED = ["ftmaster-pool", "ftop-pool", "ftodefender-pool", "flora-pool", "dms-btt-pool"]
ABL = ["fever-ll-local", "fever-ll-novol", "fever-noml", "fever-fl-ll-noing"]
UHT = ["none", "ftmaster", "dms-btt", "rdefender", FEVER]
S3, S5 = [4160, 4161, 4162], [4160, 4161, 4162, 4163, 4164]
NAMES = {"A2": "G2", "A4": "Mimic", "A5": "Spoof", "A6": "Slow", "A7": "Pulse", "E9P": "Aware", "EVX": "EVX",
         "benign": "benign"}
# Section 5: (trace, traffic) -> (methods, seeds).
CELLS = {}
for v in ("A2", "A5", "A7", "benign"):
    CELLS[("T1B", v)] = (["none"] + SIX + [FEVER], S3)
for v in ("A4", "E9P"):
    CELLS[("T1B", v)] = (["none"] + SIX + [FEVER] + POOLED + ABL, S5)
for v in ("A6", "EVX"):
    CELLS[("T1B", v)] = (["none"] + SIX + [FEVER] + POOLED, S5)
CELLS[("T1B", "A2")] = (CELLS[("T1B", "A2")][0] + ABL, S3)
for v in ("A2", "A4", "E9P", "benign"):
    CELLS[("UHt", v)] = (UHT, S3)
LONG = {("T1B", v): ([FEVER, "dms-btt", "ftmaster"], [4160]) for v in ("A4", "E9P")}   # 600 s check
OCC = "occupancy"
MEASURES = [("benign_harmed_pct", "Harm %", 3), (OCC, "Attack occupancy %", 2),
            ("probe_post_success_pct", "Probe success %", 1), ("benign_packet_in_lost_pct", "Lost first packets %", 2)]
EXTRA = ["benign_refused_at_least_once_pct", "benign_never_installed_pct", "benign_dropped_by_rule_pct",
         "attack_share_avg_pct_s11", "attack_share_avg_pct_s12", "attack_share_avg_pct_s13",
         "attack_share_max_pct_s11", "attack_share_max_pct_s12", "attack_share_max_pct_s13", "benign_deleted_per_min",
         "benign_deleted_flows_pct", "hosts_blocked_attack", "hosts_blocked_benign", "sources_blocked_attack",
         "sources_blocked_benign", "first_attack_block_s", "decision_ms_mean", "ctrl_cpu_pct", "ctrl_rss_mb",
         "packet_in", "table_full"]
ZERO = ("hosts_blocked_attack", "hosts_blocked_benign", "sources_blocked_attack", "sources_blocked_benign",
        "ingress_drops")


def name(trace, v, d, s, long=False):
    return f"{TAG}{'600' if long else ''}_{trace}_{v}_{d}_s{s}"


def summary(d):
    p = os.path.join(d, "summary.txt")
    if not os.path.exists(p):
        return None
    r = {}
    for line in open(p):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not m:
            continue
        k, v = m[1], m[2]
        if k == "decision_ms":
            r["decision_ms_mean"] = float(re.match(r"mean (\S+),", v)[1])
            continue
        try:
            r[k] = float(v)
        except ValueError:
            r[k] = v
    if "benign_harmed_pct" not in r:
        return None
    for k in ZERO:
        r.setdefault(k, 0.0)            # written only when non-zero
    sh = [r.get(f"attack_share_avg_pct_s1{i}") for i in (1, 2, 3)]
    r[OCC] = mean(sh) if all(isinstance(x, float) for x in sh) else None
    cpu, rss = [], []
    for f, out, col in (("cpu_pidstat.txt", cpu, 7), ("mem_pidstat.txt", rss, 6)):
        fp = os.path.join(d, f)
        if os.path.exists(fp):
            for line in open(fp):
                w = line.split()
                if w and w[-1].startswith("python3") and len(w) > col + 1:
                    try:
                        out.append(float(w[col + 1]))   # after the two time fields "hh:mm:ss AM"
                    except ValueError:
                        pass
    r["ctrl_cpu_pct"] = mean(cpu) if cpu else None
    r["ctrl_rss_mb"] = max(rss) / 1024 if rss else None
    return r


def sign_p(wins, n):
    return sum(comb(n, k) for k in range(wins, n + 1)) / 2 ** n if n else 1.0


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, (len(ps) - rank) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def num(x):
    return isinstance(x, float)


runs = {}
for (tr, v), (ms, seeds) in CELLS.items():
    for d in ms:
        for s in seeds:
            runs[(tr, v, d, s)] = summary(os.path.join(RUNS, name(tr, v, d, s)))
long_runs = {(tr, v, d, s): summary(os.path.join(RUNS, name(tr, v, d, s, True)))
             for (tr, v), (ms, seeds) in LONG.items() for d in ms for s in seeds}
missing = sorted(k for k, r in runs.items() if r is None) + sorted(("600 s",) + k for k, r in long_runs.items() if r is None)


def pairs(key, comp, cells):
    """(attack, seed, FEVER's value, comparator's value) over the cells; missing runs counted."""
    out, lost = [], 0
    for tr, v, seeds in cells:
        for s in seeds:
            a, b = runs.get((tr, v, FEVER, s)), runs.get((tr, v, comp, s))
            if a is None or b is None or not num(a.get(key)) or not num(b.get(key)):
                lost += 1
                continue
            out.append((v, s, a[key], b[key]))
    return out, lost


T1B_ATT = [("T1B", "A2", S3), ("T1B", "A5", S3), ("T1B", "A7", S3), ("T1B", "A4", S5), ("T1B", "E9P", S5)]
HARD = [("T1B", "A4", S5), ("T1B", "E9P", S5)]
HELD = [("T1B", "A6", S5), ("T1B", "EVX", S5)]
UH_ATT = [("UHt", "A2", S3), ("UHt", "A4", S3), ("UHt", "E9P", S3)]
TESTS = ([("H1", "benign_harmed_pct", c, T1B_ATT) for c in SIX]
         + [("H2", OCC, c, T1B_ATT) for c in SIX]
         + [("H3", "probe_post_success_pct", c, T1B_ATT) for c in SIX]
         + [("H4", OCC, c, HARD) for c in POOLED]
         + [("H5", OCC, c, HELD) for c in SIX]
         + [("H5", OCC, c, UH_ATT) for c in ("ftmaster", "dms-btt", "rdefender")]
         + [("H6", OCC, "fever-ll-local", HARD)])
assert len(TESTS) == 33
MARGIN = {"benign_harmed_pct": 0.1, OCC: 2.0, "probe_post_success_pct": 5.0}

rows = []
for h, key, comp, cells in TESTS:
    pr, lost = pairs(key, comp, cells)
    if key == "probe_post_success_pct":       # H3, non-inferiority: FEVER > comparator - 5
        win = [f > c - 5.0 for _, _, f, c in pr]
        tie = [False] * len(pr)
    else:                                     # lower is better; a tie counts against FEVER
        win = [f < c for _, _, f, c in pr]
        tie = [f == c for _, _, f, c in pr]
    contra = []
    for v in dict.fromkeys(p[0] for p in pr):
        fm, cm = mean(p[2] for p in pr if p[0] == v), mean(p[3] for p in pr if p[0] == v)
        worse = (cm - fm) if key == "probe_post_success_pct" else (fm - cm)
        if worse > MARGIN[key]:
            contra.append(NAMES[v])
    rows.append(dict(hypothesis=h, measure=key, comparator=comp, trace=cells[0][0], n=len(pr), missing_pairs=lost,
                     wins=sum(win), ties=sum(tie), fever_mean=mean(p[2] for p in pr) if pr else None,
                     comp_mean=mean(p[3] for p in pr) if pr else None, p=sign_p(sum(win), len(pr)),
                     contradicting=", ".join(contra)))
for r, a in zip(rows, holm([r["p"] for r in rows])):
    r["p_holm"] = a
    r["test_passes"] = a < 0.05
    r["supported"] = r["test_passes"] and not r["contradicting"]

os.makedirs(OUT, exist_ok=True)
allr = [(("300 s",) + k, r) for k, r in runs.items()] + [(("600 s",) + k, r) for k, r in long_runs.items()]
with open(os.path.join(OUT, "runs.csv"), "w", newline="") as f:
    w = csv.writer(f)
    cols = [m[0] for m in MEASURES] + EXTRA
    w.writerow(["length", "trace", "traffic", "method", "seed"] + cols)
    for k, r in sorted(allr, key=lambda x: str(x[0])):
        w.writerow(list(k) + ([r.get(c, "") if r else "missing" for c in cols]))
with open(os.path.join(OUT, "tests.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)


def fmt(x, n):
    return f"{x:.{n}f}" if num(x) else "-"


def stats(xs):
    xs = [x for x in xs if num(x)]
    return (mean(xs), min(xs), max(xs)) if xs else (None, None, None)


L = ["# Final testbed campaign: preregistered analysis", "",
     f"testbed/analyze_final.py, from {sum(r is not None for r in runs.values())} of {len(runs)} 300 s runs and "
     f"{sum(r is not None for r in long_runs.values())} of {len(long_runs)} 600 s runs in {RUNS} ({TAG}_*). "
     "One-sided exact sign tests, ties against FEVER, Holm over all 33 tests, alpha 0.05; supported only if the "
     "test passes and no attack contradicts it (section 7).", "",
     "## Tests (H1-H6)", "",
     "| H | Measure | Comparator | Trace | Pairs | Missing | Wins | Ties | FEVER mean | Comparator mean | p | p (Holm) "
     "| Contradicting attacks | Supported |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['hypothesis']} | {r['measure']} | {r['comparator']} | {r['trace']} | {r['n']} | {r['missing_pairs']} "
             f"| {r['wins']} | {r['ties']} | {fmt(r['fever_mean'], 3)} | {fmt(r['comp_mean'], 3)} | {r['p']:.4f} | "
             f"{r['p_holm']:.4f} | {r['contradicting'] or '-'} | {'yes' if r['supported'] else 'no'} |")
# H4's weaker reading if it fails: FEVER's mean occupancy within 2 points of each pooled baseline's on A4 and E9P.
L += ["", "H4, weaker reading (reported, not tested): FEVER's mean occupancy within 2 points of each pooled "
      "baseline's, on A4 and on E9P.", "", "| Pooled baseline | A4: FEVER / pooled | E9P: FEVER / pooled | Within 2 on both |",
      "|---|---|---|---|"]
for c in POOLED:
    cells, ok = [], True
    for v in ("A4", "E9P"):
        fm = stats([runs[("T1B", v, FEVER, s)][OCC] for s in S5 if runs[("T1B", v, FEVER, s)]])[0]
        cm = stats([runs[("T1B", v, c, s)][OCC] for s in S5 if runs[("T1B", v, c, s)]])[0]
        cells.append(f"{fmt(fm, 2)} / {fmt(cm, 2)}")
        ok &= num(fm) and num(cm) and abs(fm - cm) <= 2.0
    L.append(f"| {c} | {cells[0]} | {cells[1]} | {'yes' if ok else 'no'} |")
# H7: bars, not tests.
L += ["", "## H7 (bars, not tests)", ""]
for tr in ("T1B", "UHt"):
    b = [runs[(tr, "benign", FEVER, s)] for s in S3 if runs[(tr, "benign", FEVER, s)]]
    hm = stats([r["benign_harmed_pct"] for r in b])[0]
    lm = stats([r["benign_packet_in_lost_pct"] for r in b])[0]
    L.append(f"- {tr} benign-only, FEVER ({len(b)} runs): mean harm {fmt(hm, 3)} % (bar 0.1), mean lost first "
             f"packets {fmt(lm, 2)} % (bar 1): {'pass' if num(hm) and num(lm) and hm <= 0.1 and lm <= 1 else 'fail'}")
bad = [(k, r["hosts_blocked_benign"]) for k, r in runs.items() if k[2] == FEVER and r and r["hosts_blocked_benign"] > 0]
L.append(f"- Benign hosts blocked by FEVER, any run: {sum(int(n) for _, n in bad)} "
         f"({'pass' if not bad else 'fail: ' + ', '.join(f'{k[0]} {k[1]} s{k[3]}' for k, _ in bad)})")

# Section 8: per attack, every method and measure, and FEVER's paired differences.
L += ["", "## Per attack (section 8)", ""]
for (tr, v), (ms, seeds) in CELLS.items():
    L += [f"### {tr}, {NAMES[v]} ({v}), seeds {seeds[0]}-{seeds[-1]}", "",
          "| Method | Runs | " + " | ".join(f"{m[1]} mean (min-max)" for m in MEASURES) +
          " | Benign deleted / min | Attack hosts / sources blocked | Benign hosts / sources blocked | First block s "
          "| Decision ms | Ctrl CPU % | Ctrl RSS MB |", "|---|---|" + "---|" * (len(MEASURES) + 7)]
    for d in ms:
        rs = [runs[(tr, v, d, s)] for s in seeds if runs[(tr, v, d, s)]]
        cells = []
        for k, _, n in MEASURES:
            m, lo, hi = stats([r.get(k) for r in rs])
            cells.append(f"{fmt(m, n)} ({fmt(lo, n)}-{fmt(hi, n)})")
        ex = [stats([r.get(k) for r in rs])[0] for k in
              ("benign_deleted_per_min", "hosts_blocked_attack", "sources_blocked_attack", "hosts_blocked_benign",
               "sources_blocked_benign", "first_attack_block_s", "decision_ms_mean", "ctrl_cpu_pct", "ctrl_rss_mb")]
        L.append(f"| {d} | {len(rs)} | " + " | ".join(cells) + f" | {fmt(ex[0], 1)} | {fmt(ex[1], 1)} / {fmt(ex[2], 1)} | "
                 f"{fmt(ex[3], 1)} / {fmt(ex[4], 1)} | {fmt(ex[5], 1)} | {fmt(ex[6], 0)} | {fmt(ex[7], 1)} | {fmt(ex[8], 0)} |")
    if v == "benign":
        L.append("")
        continue
    L += ["", "FEVER minus each method, paired by seed: mean (min-max), FEVER's wins (lower harm and occupancy, "
          "higher probe success).", "", "| Method | " + " | ".join(m[1] for m in MEASURES) + " |",
          "|---|" + "---|" * len(MEASURES)]
    for d in ms:
        if d == FEVER:
            continue
        cells = []
        for k, _, n in MEASURES:
            df = [(runs[(tr, v, FEVER, s)][k], runs[(tr, v, d, s)][k]) for s in seeds
                  if runs[(tr, v, FEVER, s)] and runs[(tr, v, d, s)] and num(runs[(tr, v, FEVER, s)].get(k))
                  and num(runs[(tr, v, d, s)].get(k))]
            m, lo, hi = stats([a - b for a, b in df])
            wins = sum((a > b) if k == "probe_post_success_pct" else (a < b) for a, b in df)
            cells.append(f"{fmt(m, n)} ({fmt(lo, n)}-{fmt(hi, n)}), {wins}/{len(df)}")
        L.append(f"| {d} | " + " | ".join(cells) + " |")
    L.append("")

# Bootstrap 95 % intervals over seeds of FEVER's difference to DMS-BTT and FTMaster, per attack.
L += ["## Bootstrap 95 % intervals of FEVER minus DMS-BTT and FTMaster (over seeds, 10,000 resamples)", "",
      "| Trace | Attack | Comparator | " + " | ".join(m[1] for m in MEASURES) + " |", "|---|---|---|" + "---|" * len(MEASURES)]
rng = random.Random(4160)
for (tr, v), (ms, seeds) in CELLS.items():
    if v == "benign":
        continue
    for c in ("dms-btt", "ftmaster"):
        if c not in ms:
            continue
        cells = []
        for k, _, n in MEASURES:
            df = [runs[(tr, v, FEVER, s)][k] - runs[(tr, v, c, s)][k] for s in seeds
                  if runs[(tr, v, FEVER, s)] and runs[(tr, v, c, s)] and num(runs[(tr, v, FEVER, s)].get(k))
                  and num(runs[(tr, v, c, s)].get(k))]
            if not df:
                cells.append("-")
                continue
            bs = sorted(mean(rng.choice(df) for _ in df) for _ in range(10000))
            cells.append(f"{fmt(mean(df), n)} [{fmt(bs[249], n)}, {fmt(bs[9749], n)}]")
        L.append(f"| {tr} | {NAMES[v]} | {c} | " + " | ".join(cells) + " |")

# Ablations against FEVER (A2, A4, E9P), and FEVER without the detector against rDefender.
L += ["", "## Ablations against FEVER, paired wins of FEVER (section 8)", "",
      "| Attack | Ablation | " + " | ".join(m[1] for m in MEASURES) + " |", "|---|---|" + "---|" * len(MEASURES)]
for v, seeds in (("A2", S3), ("A4", S5), ("E9P", S5)):
    for a in ABL + ["fever-noml vs rdefender"]:
        x, y = (a, FEVER) if a in ABL else ("rdefender", "fever-noml")
        cells = []
        for k, _, n in MEASURES:
            pr = [(runs[("T1B", v, y, s)][k], runs[("T1B", v, x, s)][k]) for s in seeds
                  if runs[("T1B", v, y, s)] and runs[("T1B", v, x, s)] and num(runs[("T1B", v, y, s)].get(k))
                  and num(runs[("T1B", v, x, s)].get(k))]
            wins = sum((p > q) if k == "probe_post_success_pct" else (p < q) for p, q in pr)
            cells.append(f"{fmt(stats([p for p, _ in pr])[0], n)} / {fmt(stats([q for _, q in pr])[0], n)}, {wins}/{len(pr)}")
        lab = a if a in ABL else "fever-noml vs rdefender"
        L.append(f"| {NAMES[v]} | {lab} | " + " | ".join(cells) + " |")
L += ["", "Cells: first method's mean / second's mean, first's wins. For an ablation the first is FEVER; in the "
      "last row of each attack it is FEVER without the detector (fever-noml), against rDefender."]

# 600 s check.
L += ["", "## 600 s check (seed 4160, not tested)", "", "| Attack | Method | " + " | ".join(m[1] for m in MEASURES) + " |",
      "|---|---|" + "---|" * len(MEASURES)]
for (tr, v), (ms, seeds) in LONG.items():
    for d in ms:
        r = long_runs[(tr, v, d, seeds[0])]
        L.append(f"| {NAMES[v]} | {d} | " + " | ".join(fmt(r.get(k) if r else None, n) for k, _, n in MEASURES) + " |")
L += ["", f"## Missing runs ({len(missing)})", ""] + [f"- {' '.join(map(str, k))}" for k in missing]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:50]))
