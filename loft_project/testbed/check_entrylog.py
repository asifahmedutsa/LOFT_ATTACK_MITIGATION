"""Offline checks of the entry log, no testbed needed.

parity  run one simulator episode (T1, A4), write its polls in the controller's entry-log format,
        rebuild the features with testbed/entrylog.py and compare them with the simulator's own
        (must be identical on the wall clock; the simulator polls exactly every 1 s, so the poll
        clock must match too).
cost    time the controller's per-poll write (_log_entries) for 3,500 entries.
fake    write simulator runs as recorded testbed runs (e11tb_T1_<v>_none_s<seed>, the same log on
        s11-s13) to test testbed/e11_testbed.py end to end: its tb-wall rows must match its sim rows.

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/check_entrylog.py
    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/check_entrylog.py fake <dir> A4,benign 4130
"""
import csv
import ipaddress
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylog  # noqa: E402
from loftbench import sim  # noqa: E402
from loftbench.config import VARIANTS, SimConfig  # noqa: E402
from loftbench.trace import TRACE_DOMAIN_IDX, TRACE_DOMAINS  # noqa: E402
from loftbench.traffic import build_traffic  # noqa: E402


def parity(variant="A4", seed=4130):
    cfg = SimConfig(duration=120.0)
    tr = build_traffic(TRACE_DOMAINS["T1"], TRACE_DOMAIN_IDX["T1"], VARIANTS[variant], seed,
                       cfg.duration, cfg.attack_start)
    d = tempfile.mkdtemp()
    base = os.path.join(d, "switch_T1_s11")
    f = open(base + "_entries.bin", "wb")
    ref = []

    class Rec(entrylog.FeatureTracker):
        def observe(self, t, fids, pkts, bytes_, install_t, installs):
            entrylog.write_record(f, t, fids, pkts, bytes_, install_t, installs)
            X, dms, st = super().observe(t, fids, pkts, bytes_, install_t, installs)
            ref.append((X.copy(), dms.copy()))
            return X, dms, st

    orig = sim.FeatureTracker
    sim.FeatureTracker = Rec
    try:
        sim.run_episode(tr, cfg, collect=lambda *a: None, record_ts=False)
    finally:
        sim.FeatureTracker = orig
    f.close()
    with open(base + "_keys.csv", "w", newline="") as k:
        w = csv.writer(k)
        w.writerow(["fid", "src", "dst", "proto", "sport", "dport", "mac", "port"])
        for fid, s in enumerate(tr.flow_src.tolist()):
            w.writerow([fid, str(ipaddress.IPv4Address(int(s) & 0xFFFFFFFF)), "10.0.0.1", 17, fid, 1, "", 0])
    # every flow labelled benign so build() keeps all rows in poll order
    with open(os.path.join(d, "truth_x.csv"), "w", newline="") as k:
        w = csv.writer(k)
        w.writerow(["src", "dst", "proto", "sport", "dport", "label", "t_first"])
        for fid, s in enumerate(tr.flow_src.tolist()):
            w.writerow([str(ipaddress.IPv4Address(int(s) & 0xFFFFFFFF)), "10.0.0.1", 17, fid, 1, 0, 0])
    X0 = np.concatenate([r[0] for r in ref])
    D0 = np.concatenate([r[1] for r in ref])
    for clock in ("wall", "poll"):
        b = entrylog.build(d, clock=clock)
        dx = float(np.abs(b["X"] - X0).max()) if len(X0) else 0.0
        dd = float(np.abs(b["dms"] - D0).max()) if len(D0) else 0.0
        print(f"parity {clock}: {len(ref)} polls, {len(X0)} rows, max |dX| {dx:.3g}, max |d dms| {dd:.3g}")
        assert b["X"].shape == X0.shape and dx < 1e-4 and dd < 1e-3, clock


def fake(out, variants, seed):
    from loftbench.config import attack_variant
    cfg = SimConfig(duration=300.0)
    for v in variants:
        tr = build_traffic(TRACE_DOMAINS["T1"], TRACE_DOMAIN_IDX["T1"],
                           None if v == "benign" else attack_variant(v), seed, cfg.duration, cfg.attack_start)
        d = os.path.join(out, f"e11tb_T1_{v}_none_s{seed}")
        os.makedirs(d, exist_ok=True)
        f = open(os.path.join(d, "switch_T1_s11_entries.bin"), "wb")

        class Rec(entrylog.FeatureTracker):
            def observe(self, t, fids, pkts, bytes_, install_t, installs):
                entrylog.write_record(f, t, fids, pkts, bytes_, install_t, installs)
                return super().observe(t, fids, pkts, bytes_, install_t, installs)
        orig = sim.FeatureTracker
        sim.FeatureTracker = Rec
        try:
            sim.run_episode(tr, cfg, collect=lambda *a: None, record_ts=False)
        finally:
            sim.FeatureTracker = orig
        f.close()
        ips = [str(ipaddress.IPv4Address(int(x) & 0xFFFFFFFF)) for x in tr.flow_src.tolist()]
        with open(os.path.join(d, "switch_T1_s11_keys.csv"), "w", newline="") as k:
            w = csv.writer(k)
            w.writerow(["fid", "src", "dst", "proto", "sport", "dport", "mac", "port"])
            for fid, ip in enumerate(ips):
                w.writerow([fid, ip, "10.1.0.100", 17, fid, 1, "", 0])
        with open(os.path.join(d, "truth_d1h1.csv"), "w", newline="") as k:
            w = csv.writer(k)
            w.writerow(["src", "dst", "proto", "sport", "dport", "label", "t_first"])
            for fid, ip in enumerate(ips):
                w.writerow([ip, "10.1.0.100", 17, fid, 1, int(tr.flow_attack[fid]), 0])
        for sw in ("s12", "s13"):
            for ext in ("_entries.bin", "_keys.csv"):
                os.symlink(f"switch_T1_s11{ext}", os.path.join(d, f"switch_T1_{sw}{ext}"))
        open(os.path.join(d, "summary.txt"), "w").write("fake run from the simulator\n")
        print("wrote", d)


def cost(n=3500, reps=200):
    d = tempfile.mkdtemp()
    f = open(os.path.join(d, "e.bin"), "wb")
    fids = np.arange(n, dtype=np.int64)
    pk = np.random.randint(1, 1000, n).astype(np.int64)
    by, inst = pk * 500, np.random.rand(n) * 300
    t0 = time.perf_counter()
    for i in range(reps):
        entrylog.write_record(f, float(i), fids, pk, by, inst, 10)
        f.flush()
    ms = 1000 * (time.perf_counter() - t0) / reps
    print(f"cost: {ms:.3f} ms per poll for {n} entries ({28 * n / 1024:.0f} KiB)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fake":
        fake(sys.argv[2], sys.argv[3].split(","), int(sys.argv[4]))
    else:
        parity()
        cost()
