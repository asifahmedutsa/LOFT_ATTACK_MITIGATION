"""Exploratory 600 s runs (amendment 2 of the final campaign's preregistration): FEVER, DMS-BTT and
FTMaster on T1B Mimic (A4) and Aware (E9P), seed 4160, with a replay that loops past one pass.

Not part of the preregistered analysis and no test is run: one seed per cell. The measures are those
of testbed/analyze_final.py over the traffic window (probe start + 600 s), and, to see whether a
method holds over the longer run, the same measures for the first and the second 300 s of traffic.
"""
import csv
import glob
import os
from statistics import mean

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_final.py")
_code = open(SRC).read()
exec(compile(_code[:_code.index("\ndef sign_p")], SRC, "exec"))   # num, traffic_window, occupancy_window, summary

DUR = 600
ATTACK = 50.0
DEFS = [FEVER, "dms-btt", "ftmaster"]
OUTF = os.path.join(os.path.dirname(SRC), "..", "results", "testbed_prereg_final", "exploratory_600s.md")


def probe_success(d, lo, hi):
    t0 = float(open(glob.glob(os.path.join(d, "controller_*_t0.txt"))[0]).read())
    with open(glob.glob(os.path.join(d, "probe_*.csv"))[0]) as f:
        q = [x for x in csv.DictReader(f) if lo <= float(x["t_wall"]) - t0 < hi]
    return 100 * sum(x["ok"] == "1" for x in q) / len(q) if q else None


def occ(d, lo, hi):
    sh = list(occupancy_window(d, hi, attack_start=lo).values())
    return mean(sh) if sh and all(isinstance(x, float) for x in sh) else None


def blocks(d):
    """First host block of each attacker host (controller time, s)."""
    t = {}
    with open(glob.glob(os.path.join(d, "controller_*_flows.csv"))[0]) as fh:
        for x in csv.DictReader(fh):
            if x["event"] == "host_block":
                t.setdefault(x["src"][-2:], float(x["t"]))
    return " / ".join(f"{t[h]:.0f}" if h in t else "–" for h in ("05", "06"))


def outage(d, n=20):
    """Probe outage: the first failed attempt after the attack's start, and the start of the unbroken
    run of successes that lasts to the end of the probe, if at least n long (s, controller time)."""
    t0 = float(open(glob.glob(os.path.join(d, "controller_*_t0.txt"))[0]).read())
    with open(glob.glob(os.path.join(d, "probe_*.csv"))[0]) as fh:
        q = [(float(x["t_wall"]) - t0, x["ok"] == "1") for x in csv.DictReader(fh)]
    f = next((i for i, (t, ok) in enumerate(q) if t >= ATTACK and not ok), None)
    if f is None:
        return "none"
    last = max(i for i, (_, ok) in enumerate(q) if not ok)
    return f"{q[f][0]:.0f}–{q[last + 1][0]:.0f}" if len(q) - last - 1 >= n else f"{q[f][0]:.0f}–"


def measures(d):
    r = summary(d, dur=DUR)
    if r is None:
        return None
    s, e = traffic_window(d, DUR)
    mid = s + DUR / 2
    r["probe_h1"], r["probe_h2"] = probe_success(d, ATTACK, mid), probe_success(d, mid, e)
    r["occ_h1"], r["occ_h2"] = occ(d, ATTACK, mid), occ(d, mid, e)
    r["blocks"] = blocks(d)
    r["outage"] = outage(d)
    return r


def campaign(v, m):
    """The same cell in the 300 s campaign, seed 4160 (results/testbed_prereg_final/runs.csv)."""
    with open(os.path.join(os.path.dirname(OUTF), "runs.csv")) as fh:
        for x in csv.DictReader(fh):
            if (x["length"], x["trace"], x["traffic"], x["method"], x["seed"]) == ("300 s", "T1B", v, m, "4160"):
                return x
    return None


def f(x, n=2):
    return "–" if x is None else f"{x:.{n}f}"


rows = []
for v in ("A4", "E9P"):
    for m in DEFS:
        d = os.path.join(RUNS, f"exp600_T1B_{v}_{m}_s4160")
        rows.append((v, m, measures(d)))
# The first A4 FEVER run overlapped a reinstall of the (unchanged) testbed code and was redone; it is
# not counted, and is shown below only for the spread between two runs of one seed.
old = sorted(glob.glob(os.path.join(RUNS, "_failed", f"exp600_T1B_A4_{FEVER}_s4160.overlapped_install.*")))
old = measures(old[0]) if old else None

L = ["# Exploratory 600 s runs", "",
     "Amendment 2 of the final campaign's preregistration: the six preregistered 600 s runs could not "
     "run (one T1B replay pass is 343 s at the campaign's rate) and are reported missing. These six runs "
     "were made afterwards with a replay that loops past one pass, on the same deployed models, tree3, "
     "benign scale 0.5 and seed 4160. One seed per cell, so no test is made and nothing here enters the "
     "preregistered results.", "",
     "Measures as in the campaign, over the traffic window (probe start + 600 s). The first half is from "
     "the attack's start at 50 s to the middle of the traffic, the second half the remaining 300 s.", "",
     "| Trace | Variant | Method | Harm % | Occupancy % | Probe success % | Benign deletes/min | Decision ms "
     "| Occ. 1st / 2nd half % | Probe 1st / 2nd half % | Hosts 5 / 6 blocked at s | Probe outage s "
     "| 300 s run: occ. / probe % / first block s / outage s |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for v, m, r in rows + ([("A4", FEVER + " (excluded run)", old)] if old else []):
    if r is None:
        L.append(f"| T1B | {NAMES[v]} | {m} | missing | | | | | | | | | |")
        continue
    c = campaign(v, m.split()[0])
    cs = (f"{f(float(c['occupancy']))} / {f(float(c['probe_post_success_pct']), 1)} / "
          + (f"{float(c['first_attack_block_s']) + ATTACK:.0f}" if c["first_attack_block_s"] else "–")
          + " / " + outage(os.path.join(RUNS, f"fin_T1B_{v}_{m.split()[0]}_s4160"))) if c else "–"
    L.append(f"| T1B | {NAMES[v]} | {m} | {f(r['benign_harmed_pct'], 3)} | {f(r[OCC])} "
             f"| {f(r['probe_post_success_pct'], 1)} | {f(r.get('benign_deleted_per_min'))} "
             f"| {f(r.get('decision_ms_mean'), 0)} | {f(r['occ_h1'])} / {f(r['occ_h2'])} "
             f"| {f(r['probe_h1'], 1)} / {f(r['probe_h2'], 1)} | {r['blocks']} | {r['outage']} | {cs} |")
L += ["", "Block times are controller time, as is the attack's start at 50 s. The last column is the "
      "same cell in the 300 s campaign with seed 4160, over its own traffic window (260 s after the attack's "
      "start, against 300 s for the first half here). The probe outage runs from the first failed attempt "
      "after the attack's start to the last one; an open end means fewer than 20 successes after it.",
      "", "The last row is the first A4 FEVER run, which overlapped a reinstall of the unchanged testbed "
      "code and was redone. It is not counted and is shown only for the spread between two runs of one seed.",
      "", "Up to 160 s the 300 s and 600 s runs receive the same traffic: the benign flows are identical "
      "and the attack packets agree within 2 %, as rebuilt from the drivers' schedules, and the controller "
      "code and model files are those of the campaign. DMS-BTT and FTMaster behave as in their 300 s runs. "
      "FEVER does not: in its 600 s runs the attackers were blocked later and the probe outage lasted longer "
      "than in the 300 s runs, and on Mimic the outage also began earlier. The cause was not found; with one "
      "seed per cell this is a difference to check, not a result.",
      ""]
# Afterwards one 300 s run of the same cell (tag recheck), to see whether the testbed still gave the
# campaign's result on the day of the 600 s runs.
chk = os.path.join(RUNS, f"recheck_T1B_A4_{FEVER}_s4160")
rc = summary(chk) if os.path.isdir(chk) else None
if rc:
    c = campaign("A4", FEVER)
    L += [f"A 300 s check run of Mimic FEVER with seed 4160, made the same day after the 600 s runs: harm "
          f"{f(rc['benign_harmed_pct'], 3)} %, occupancy {f(rc[OCC])} %, probe success "
          f"{f(rc['probe_post_success_pct'], 1)} %, hosts 5 / 6 blocked at {blocks(chk)} s, probe outage "
          f"{outage(chk)} s. In the campaign the same run gave {f(float(c['occupancy']))} %, "
          f"{f(float(c['probe_post_success_pct']), 1)} % and a block at "
          f"{float(c['first_attack_block_s']) + ATTACK:.0f} s. The testbed thus gave close to the campaign's "
          f"result that day, and the longer outages of the 600 s FEVER runs are not explained by its state.", ""]
L += ["Controller log length (s): " + ", ".join(
    f"{NAMES[v]} {m} {f(r.get('seconds'), 0)}" for v, m, r in rows if r), ""]
open(OUTF, "w").write("\n".join(L))
print("\n".join(L))
