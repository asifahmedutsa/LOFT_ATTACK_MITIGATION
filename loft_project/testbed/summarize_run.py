"""Summarise one testbed run directory (no root needed).

    python3 testbed/summarize_run.py ~/loft-runs/tb_D1_benign_v3 [--attack-start 50]

Reports, per domain: monitored-table entries over time (before and after the attack
start), TABLE_FULL errors, Packet-Ins, installs vs distinct flows, deletes and demotes,
controller decision time, ping loss and RTT, and the flows each host sent.
"""
import argparse
import csv
import glob
import os
import re
import statistics as st


def _rows(path):
    with open(path) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]


def _stats(v):
    if not v:
        return "n/a"
    return f"mean {st.mean(v):.0f}, max {max(v):.0f}"


def summarize(d, attack_start):
    out = {}
    for log in sorted(glob.glob(os.path.join(d, "controller_*.csv"))):
        if log.endswith("_flows.csv"):
            continue
        dom = os.path.basename(log)[len("controller_"):-4]
        r = _rows(log)
        pre = [x["entries"] for x in r if x["t"] < attack_start]
        post = [x["entries"] for x in r if x["t"] >= attack_start]
        last = r[-1] if r else {}
        with open(log.replace(".csv", "_flows.csv")) as f:
            ev = list(csv.DictReader(f))
        inst = [e for e in ev if e["event"] == "install"]
        key = lambda e: tuple(e[k] for k in ("src", "dst", "proto", "sport", "dport"))  # noqa: E731
        keys = {key(e) for e in inst}
        refused = {key(e) for e in ev if e["event"] == "refused"}
        info = dict(seconds=round(last.get("t", 0)), entries_before_attack=_stats(pre),
                    entries_after_attack=_stats(post), table_full=int(last.get("table_full", 0)),
                    packet_in=int(last.get("packet_in", 0)), installs=len(inst),
                    distinct_flows_installed=len(keys), distinct_flows_refused=len(refused),
                    deletes=int(last.get("deletes", 0)),
                    demotes=int(last.get("demotes", 0)),
                    decision_ms=_stats([x["decision_ms"] for x in r]))
        ping = os.path.join(d, f"ping_{dom}.txt")
        if os.path.exists(ping):
            txt = open(ping).read()
            m = re.search(r"(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss", txt)
            rtt = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)", txt)
            if m:
                info["ping"] = f"{m.group(2)}/{m.group(1)} received, {m.group(3)}% loss"
            if rtt:
                info["rtt_ms"] = f"min {rtt.group(1)}, avg {rtt.group(2)}, max {rtt.group(3)}"
        ff = os.path.join(d, f"final_flows_{dom}.txt")
        if os.path.exists(ff):
            info["final_dump_flows_lines"] = open(ff).read().strip()
        info["_refused"], info["_installed"] = refused, keys
        out[dom] = info
    hosts, benign = {}, {}
    for t in sorted(glob.glob(os.path.join(d, "truth_*.csv"))):
        with open(t) as f:
            rows = list(csv.DictReader(f))
        h = os.path.basename(t)[6:-4]
        hosts[h] = (len(rows), sum(r["label"] == "1" for r in rows))
        # Hosts are named d<k>h<i>, k = position of the domain in --domains (1-based).
        benign.setdefault(h[1:h.index("h")], set()).update(
            tuple(r[k] for k in ("src", "dst", "proto", "sport", "dport"))
            for r in rows if r["label"] == "0")
    # Benign flows refused an entry at least once (the simulator's rejection harm), and
    # benign flows that never got an entry (needs no refusal log). Domains are matched to
    # host prefixes in sorted-name order, which equals --domains order for D1,D2,D3.
    for k, info in enumerate(out.values(), start=1):
        b = benign.get(str(k), set())
        info["benign_flows"] = len(b)
        info["benign_refused_at_least_once_pct"] = round(
            100 * len(b & info.pop("_refused")) / max(len(b), 1), 2)
        info["benign_never_installed_pct"] = round(
            100 * len(b - info.pop("_installed")) / max(len(b), 1), 2)
    return out, hosts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--attack-start", type=float, default=50.0)
    a = ap.parse_args()
    out, hosts = summarize(os.path.expanduser(a.run_dir), a.attack_start)
    for dom, info in out.items():
        print(f"== {dom}")
        for k, v in info.items():
            print(f"  {k:26s} {v}")
    print("== flows sent per host (total, attack)")
    for h, (n, na) in hosts.items():
        print(f"  {h:8s} {n:6d} {na:6d}")


if __name__ == "__main__":
    main()
