"""Read a testbed entry log (run_testbed --entry-log, LOFT_ENTRYLOG=1) and rebuild the detectors'
inputs offline: the 17 causal features and DMS-BTT's (Numb, PIT, Sizep), with the same
loftbench.features.FeatureTracker the controller runs, and a label per entry from the run's
truth files.

Files per monitored switch (next to switch_<D>_<sw>.csv):
  switch_<D>_<sw>_entries.bin  one record per poll: float64 [t, n, installs since the last poll],
                               then n int32 flow ids, n int64 packets, n int64 bytes, n float64
                               install times (the controller's clock, as the tracker gets them)
  switch_<D>_<sw>_keys.csv     fid, src, dst, proto, sport, dport, mac, port

Two clocks:
  wall   the poll times the controller saw (what the deployed detector gets, jitter included)
  poll   a warped clock in which consecutive polls are exactly 1 s apart (install times mapped
         by linear interpolation between polls): the simulator's view of the same counters.
         Comparing the two isolates the effect of poll jitter on the features.
"""
import csv
import glob
import ipaddress
import os

import numpy as np

from loftbench.features import FeatureTracker

ATTACK_MACS = {"00:00:00:00:01:05", "00:00:00:00:01:06"}


def read_entries(path):
    """Yield (t, fids, pkts, bytes, install_t, installs) per poll."""
    raw = np.fromfile(path, dtype=np.uint8)
    i = 0
    while i + 24 <= len(raw):
        t, n, inst_n = np.frombuffer(raw[i:i + 24].tobytes(), np.float64)
        n = int(n)
        i += 24
        end = i + n * 28
        if end > len(raw):
            break                                   # torn last record (run ended mid-write)
        b = raw[i:end].tobytes()
        fids = np.frombuffer(b, np.int32, n, 0).astype(np.int64)
        pk = np.frombuffer(b, np.int64, n, 4 * n)
        by = np.frombuffer(b, np.int64, n, 12 * n)
        inst = np.frombuffer(b, np.float64, n, 20 * n)
        i = end
        yield float(t), fids, pk, by, inst, int(inst_n)


def write_record(f, t, fids, pk, by, inst, installs):
    """The controller's record format (testbed/loft_ryu_app.py, _log_entries)."""
    np.array([t, len(fids), installs], np.float64).tofile(f)
    np.asarray(fids).astype(np.int32).tofile(f)
    np.asarray(pk).astype(np.int64).tofile(f)
    np.asarray(by).astype(np.int64).tofile(f)
    np.asarray(inst, np.float64).tofile(f)


def truth_labels(run_dir):
    """5-tuple (src, dst, proto, sport, dport) as strings -> label (1 = attack)."""
    lab = {}
    for p in glob.glob(os.path.join(run_dir, "truth_*.csv")):
        for r in csv.DictReader(open(p)):
            lab[(r["src"], r["dst"], r["proto"], r["sport"], r["dport"])] = int(r["label"])
    return lab


def load_keys(path, labels=None):
    """fid -> source address (int) and label (1 attack, 0 benign, -1 unknown, e.g. ping)."""
    rows = list(csv.DictReader(open(path)))
    nf = max((int(r["fid"]) for r in rows), default=-1) + 1
    src = np.zeros(nf, np.int64)
    y = np.full(nf, -1, np.int8)
    mac = np.empty(nf, dtype=object)
    for r in rows:
        f = int(r["fid"])
        src[f] = int(ipaddress.IPv4Address(r["src"]))
        mac[f] = r["mac"]
        k = (r["src"], r["dst"], r["proto"], r["sport"], r["dport"])
        if labels is not None:
            rk = (r["dst"], r["src"], r["proto"], r["dport"], r["sport"])
            y[f] = labels.get(k, labels.get(rk, -1))
            if y[f] == -1 and r["mac"] in ATTACK_MACS:
                y[f] = 1
    return src, y, mac


def build(run_dir, sw="s11", domain="T1", clock="wall", frac=1.0, seed=0, capacity=3500,
          keep_unknown=False):
    """Rows (entry x poll) for one switch of one run: dict of X, dms, y, t, interval, occ."""
    base = os.path.join(run_dir, f"switch_{domain}_{sw}")
    src, y, _ = load_keys(base + "_keys.csv", truth_labels(run_dir))
    polls = list(read_entries(base + "_entries.bin"))
    T = np.array([p[0] for p in polls])
    if clock == "poll":
        W = T[0] + np.arange(len(T), dtype=float)

        def warp(x):
            # Linear interpolation between polls, extended with slope 1 outside them.
            return np.where(x < T[0], x - T[0] + W[0],
                            np.where(x > T[-1], x - T[-1] + W[-1], np.interp(x, T, W)))
    elif clock != "wall":
        raise ValueError(clock)
    tr = FeatureTracker(len(src), src, capacity, 1.0)
    rng = np.random.default_rng(seed)
    out = {k: [] for k in ("X", "dms", "y", "t", "interval", "occ", "fid")}
    prev = None
    for k, (t, fids, pk, by, inst, installs) in enumerate(polls):
        tt, ii = (t, inst) if clock == "wall" else (float(W[k]), warp(inst))
        X, dms, _ = tr.observe(tt, fids, pk, by, ii, installs)
        gap = t - prev if prev is not None else 1.0
        prev = t
        m = rng.random(len(fids)) < frac
        if not keep_unknown:
            m &= y[fids] >= 0
        out["X"].append(X[m])
        out["dms"].append(dms[m])
        out["y"].append(y[fids][m])
        out["fid"].append(fids[m])
        for key, v in (("t", t), ("interval", gap), ("occ", len(fids) / capacity)):
            out[key].append(np.full(int(m.sum()), v))
    return {k: np.concatenate(v) if v else np.zeros(0) for k, v in out.items()}
