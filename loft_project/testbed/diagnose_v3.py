"""Post-hoc diagnosis of the prereg v3 T1 runs (read-only; finished runs with a summary only).
    python3 testbed/diagnose_v3.py [table|blocks|split|polls|all]
Exploratory, written after seeds 4120-4123: see results/testbed_prereg_v3/posthoc_diagnosis.md."""
import csv, glob, os, re, statistics as st, sys
from collections import defaultdict

R = os.path.expanduser("~/loft-runs")
ATT = {"00:00:00:00:01:05", "00:00:00:00:01:06"}


def summ(p):
    d = {}
    for l in open(p):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", l)
        if not m:
            continue
        k, v = m[1], m[2]
        if k == "decision_ms":
            a = re.findall(r"[0-9.]+", v); d["dec_mean"], d["dec_max"] = float(a[0]), float(a[1])
        else:
            try: d[k] = float(v)
            except ValueError: d[k] = v
    return d


runs = {}
for f in sorted(glob.glob(f"{R}/v3_T1_*_s41*/summary.txt")):
    n = os.path.basename(os.path.dirname(f)); _, _, v, dfn, s = n.split("_", 4)
    runs[(v, dfn, s)] = (os.path.dirname(f), summ(f))

part = sys.argv[1] if len(sys.argv) > 1 else "all"
if part in ("all", "table"):
    cols = ["benign_harmed_pct", "benign_refused_at_least_once_pct", "benign_dropped_by_rule_pct",
            "benign_packet_in_lost_pct", "probe_post_success_pct", "dec_mean", "dec_max",
            "attack_share_avg_pct_s11", "attack_share_avg_pct_s12", "attack_share_avg_pct_s13",
            "packet_in", "deletes"]
    short = ["harm", "refus", "rule", "pinLost", "probeOK", "decMs", "decMax", "Pa11", "Pa12", "Pa13",
             "pktIn", "dels"]
    for v in ("A2", "A4", "E9P", "benign"):
        print(f"\n== {v} (mean over seeds)")
        print(f"{'defense':28s}" + "".join(f"{c:>9s}" for c in short) + "   n")
        for dfn in sorted({k[1] for k in runs}):
            rs = [runs[k][1] for k in runs if k[0] == v and k[1] == dfn]
            if not rs: continue
            vals = []
            for c in cols:
                x = [r[c] for r in rs if isinstance(r.get(c), float)]
                vals.append(f"{st.mean(x):9.1f}" if x else f"{'-':>9s}")
            print(f"{dfn:28s}" + "".join(vals) + f"   {len(rs)}")

if part in ("all", "blocks"):
    print("\n== ensguard: host blocks and per-host deletes in 10 s windows (deletes = flagged + "
          "PortGuard trims + block clean-up)")
    for k in sorted(runs):
        v, dfn, s = k
        if dfn != "ensguard" or v == "benign": continue
        d, sm = runs[k]
        own = {}
        for t in glob.glob(f"{d}/truth_d1h*.csv"):
            mac = "00:00:00:00:01:%02x" % int(t[-5])
            for r in csv.DictReader(open(t)):
                own[(r["src"], r["dst"], r["proto"], r["sport"], r["dport"])] = mac
        dels = defaultdict(list); blocks = []
        for e in csv.DictReader(open(f"{d}/controller_T1_flows.csv")):
            if e["event"] == "delete":
                m = own.get((e["src"], e["dst"], e["proto"], e["sport"], e["dport"]))
                if m: dels[(e["sw"], m)].append(float(e["t"]))
            elif e["event"] == "host_block":
                blocks.append((float(e["t"]), e["src"], e["sw"]))

        def win(sw, mac, t):
            return sum(t - 10 < x <= t for x in dels.get((sw, mac), []))
        print(f"\n{v} {s}: harm {sm['benign_harmed_pct']}  blocked att/ben "
              f"{sm.get('hosts_blocked_attack', 0)}/{sm.get('hosts_blocked_benign', 0)}")
        for tb, mac, sw in blocks:
            macs = sorted({m for (w, m) in dels if w == sw})
            cnt = {m[-2:]: win(sw, m, tb) for m in macs}
            print(f"   block {mac[-2:]} {'ATTACKER' if mac in ATT else 'BENIGN'} on {sw} at {tb:.1f}s; "
                  f"deletes in prior 10 s by host: {cnt}")
        for sw in ("s11", "s12", "s13"):
            best = {}
            for m in sorted({m for (w, m) in dels if w == sw}):
                ts = sorted(dels[(sw, m)]); j = 0; b = 0
                for i, t in enumerate(ts):
                    while ts[j] <= t - 10: j += 1
                    b = max(b, i - j + 1)
                best[m[-2:]] = b
            print(f"   {sw} max deletes in any 10 s window by host: {best}")

if part in ("all", "split"):
    # Who removed the attackers' entries on s11: deletes while PortGuard can be enforcing (the
    # table reached 90 % in the last 31 s) vs while only the detector runs (70-90 % full).
    import bisect
    print("\n== s11 deletes by owner and regime (ensguard)")
    for k in sorted(runs):
        v, dfn, s = k
        if dfn != "ensguard" or v == "benign": continue
        d = runs[k][0]
        own = {}
        for f in glob.glob(f"{d}/truth_d1h*.csv"):
            for r in csv.DictReader(open(f)):
                own[(r["src"], r["dst"], r["proto"], r["sport"], r["dport"])] = f[-5]
        sw = list(csv.DictReader(open(f"{d}/switch_T1_s11.csv")))
        ts = [float(x["t"]) for x in sw]; n = [float(x["entries"]) for x in sw]
        hi = [t for t, e in zip(ts, n) if e >= 0.9 * 3500]
        c = defaultdict(int)
        for e in csv.DictReader(open(f"{d}/controller_T1_flows.csv")):
            if e["event"] != "delete" or e["sw"] != "s11": continue
            h = own.get((e["src"], e["dst"], e["proto"], e["sport"], e["dport"]))
            t = float(e["t"]); i = bisect.bisect_right(hi, t)
            pg = i > 0 and t - hi[i - 1] <= 31
            occ = n[max(bisect.bisect_right(ts, t) - 1, 0)] / 3500
            c[("att" if h in ("5", "6") else "ben" if h else "unk",
               "PG-on" if pg else "detector-only" if occ >= 0.7 else "below70")] += 1
        print(f"{v} {s}: {dict(sorted(c.items()))}")

if part in ("all", "polls"):
    print("\n== s11 poll interval after the attack start (s): mean / p95 / max; decision_ms mean")
    for v in ("A2", "A4", "E9P", "benign"):
        for dfn in sorted({k[1] for k in runs}):
            iv, dm = [], []
            for k in runs:
                if k[0] != v or k[1] != dfn: continue
                r = list(csv.DictReader(open(f"{runs[k][0]}/switch_T1_s11.csv")))
                t = [float(x["t"]) for x in r]
                for a, b, x in zip(t, t[1:], r[1:]):
                    if a >= 50: iv.append(b - a); dm.append(float(x["decision_ms"]))
            if iv:
                iv.sort()
                print(f"{v:6s} {dfn:28s} {st.mean(iv):5.2f} {iv[int(.95 * len(iv))]:5.2f} "
                      f"{iv[-1]:6.2f}   {st.mean(dm):5.0f}")
