"""Control-plane diagnostics for one testbed run (no root needed).

    python testbed/diagnose_run.py ~/loft-runs/tb_D1_A2_none_lean [--domain D1 --k 1 --seed 4000]

Reports Open vSwitch coverage deltas (rconn_overflow = messages to a controller dropped
because its queue was full), controller and ovs-vswitchd CPU from pidstat, the
controller's event backlog, and, per 50 s window of flow start time, the share of benign
flows that never got an entry (their Packet-In never reached the controller). Needs the
loftbench package (run from loft_project/ with the project venv).
"""
import argparse
import collections
import csv
import os
import re

import numpy as np

from loftbench.config import DOMAINS
from loftbench.data import DOMAIN_IDX
from loftbench.traffic import _rng, generate_benign

KEYS = ("rconn_overflow", "rconn_sent", "ofproto_recv_openflow", "ofproto_packet_out",
        "dpif_execute", "upcall_flow_limit_grew", "handler_duplicate_upcall")


def coverage(path):
    out = {}
    for line in open(path):
        m = re.match(r"(\S+)\s+[\d.]+/sec\s+[\d.]+/sec\s+[\d.]+/sec\s+total: (\d+)", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def cpu(path):
    v = collections.defaultdict(list)
    for line in open(path):
        p = line.split()
        if len(p) == 11 and p[3].isdigit():
            v[p[-1]].append(float(p[8]))
    return v


def ip(x):
    return ".".join(str((int(x) >> s) & 255) for s in (24, 16, 8, 0))


def never_installed_by_start(d, domain, k, seed):
    t, fid, _, src, _ = generate_benign(DOMAINS[domain], 300.0, DOMAIN_IDX[domain],
                                        _rng("benign", DOMAINS[domain].name, seed))
    first = np.full(fid.max() + 1, np.inf)
    np.minimum.at(first, fid, t)
    dst = f"10.{k}.0.100"
    k2t = {(ip(src[f]), dst, "17", str(1024 + (f * 7919) % 60000), str(1 + (f * 104729) % 1023)):
           first[f] for f in range(len(first))}
    key = lambda r: (r["src"], r["dst"], r["proto"], r["sport"], r["dport"])  # noqa: E731
    inst = {key(r) for r in csv.DictReader(open(os.path.join(d, f"controller_{domain}_flows.csv")))
            if r["event"] == "install"}
    st = np.array(list(k2t.values()))
    miss = np.array([kk not in inst for kk in k2t])
    return {f"{lo}-{lo + 50}s": round(float(100 * miss[(st >= lo) & (st < lo + 50)].mean()), 1)
            for lo in range(0, 300, 50)}, round(float(100 * miss.mean()), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--domain", default="D1")
    ap.add_argument("--k", type=int, default=1, help="position of the domain in --domains")
    ap.add_argument("--seed", type=int, default=4000)
    a = ap.parse_args()
    d = os.path.expanduser(a.run_dir)
    b, e = (coverage(os.path.join(d, f"ovs_coverage_{w}.txt")) for w in ("before", "after"))
    print("Open vSwitch coverage during the run:")
    for k in KEYS:
        print(f"  {k:26s} {e.get(k, 0) - b.get(k, 0)}")
    print("CPU (% of one core), 120-300 s of the run:")
    for name, v in cpu(os.path.join(d, "cpu_pidstat.txt")).items():
        w = v[120:300]
        print(f"  {name:14s} mean {np.mean(w):5.1f}   samples >= 95 %: {np.mean(np.array(w) >= 95):.2f}")
    r = list(csv.DictReader(open(os.path.join(d, f"controller_{a.domain}.csv"))))
    if r and "event_backlog" in r[0]:
        bl = [float(x["event_backlog"]) for x in r if 120 <= float(x["t"]) <= 300]
        print(f"controller event backlog 120-300 s: mean {np.mean(bl):.0f}, max {max(bl):.0f}")
    last = r[-1]
    print(f"Packet-Ins handled {last['packet_in']}, installs {last['installs']}, "
          f"TABLE_FULL {last['table_full']}")
    by, total = never_installed_by_start(d, a.domain, a.k, a.seed)
    print(f"benign flows never installed: {total} % overall; by flow start time: {by}")


if __name__ == "__main__":
    main()
