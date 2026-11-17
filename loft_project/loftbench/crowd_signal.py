"""Can a controller tell a benign flash crowd from a low-rate flow table overflow attack by whether a
host's entries are refreshed? (Exploratory, offline; before any preregistration of a crowd guard.)

A low-rate attacker keeps each entry alive by sending a packet before the idle timeout, again and
again. A crowd flow sends a few packets and goes quiet. At the controller's 1 s polls, an entry is
"refreshed" when its packet counter rises after at least IDLE_POLLS polls without change, while the
entry is still alive (gap below the idle timeout). Feature `idle_polls` of loftbench.features is the
same count.

Rebuilds the exact packet schedules the testbed hosts sent (loftbench.traffic.build_traffic, as
testbed/traffic_driver.py does) for T1B at benign scale 0.5: the round-2 crowds (F2, F2H, seed 4187)
and every campaign attack (seed 4160). For each kind of flow it reports, per host, the share of flows
that were refreshed within their first REFRESH_BY seconds, and the time to the first refresh.

Gate G0 of docs/crowdguard_prereg.md (section 3): a flow is refreshed when a packet of it comes at least
G_MIN s and less than IDLE s after its previous packet; a host's refresh share at time t is the share
of its flows seen in (t - WINDOW, t] that were refreshed at least once by t. G0 passes if the crowd
host's share stays at most 0.3 during each crowd and the 10 s after it (F2H, seed 4187), and every
attacker host's share is at least 0.7 from 20 s after the attack starts to the end of the run, for all
seven attacks (seed 4160). Seconds in which a host has no flow in the window are skipped.

    PYTHONPATH=. ~/.venvs/loft/bin/python -B -m loftbench.crowd_signal   # writes results/crowd_signal/report.md
"""
import dataclasses
import os

import numpy as np

from .config import attack_variant
from .data import profile_of
from .ports import assign_ports
from .traffic import KIND_CODE, build_traffic

OUT = "results/crowd_signal"
IDLE = 10.0          # switch idle timeout (s)
IDLE_POLLS = 2       # polls without change before a packet counts as a refresh
REFRESH_BY = 20.0    # look at each flow's first 20 s
G_MIN = 2.0         # G0: shortest gap that counts as a refresh (s)
WINDOW = 30.0       # G0: refresh share over the host's flows seen in the last 30 s
DUR = 300
CROWD_HOST = 2      # F<k>H: benign host 2 (d1h3) sends every crowd flow
ATTACKS = ["A2", "A5", "A7", "A4", "E9P", "A6", "EVX"]
NAME = {"A2": "G2", "A5": "Spoof", "A7": "Pulse", "A4": "Mimic", "E9P": "Aware", "A6": "Slow", "EVX": "EVX"}


def schedule(variant, seed, crowd=None, one_host=False):
    prof, didx = profile_of("T1B")
    if hasattr(prof, "loop"):
        prof = dataclasses.replace(prof, loop=True)
    prof = dataclasses.replace(prof, rate_pps=0.5 * prof.rate_pps)
    if crowd:
        prof = dataclasses.replace(prof, flash_mult=float(crowd))
    tr = build_traffic(prof, didx, attack_variant(variant) if variant else None, seed, 300.0, 50.0)
    tr = assign_ports(tr, "dedicated")
    if one_host:
        tr.flow_port[tr.flow_kind == KIND_CODE["flash"]] = CROWD_HOST
    return tr


def host_share(tr, port):
    """Per second t = 0..DUR: (flows of the host seen in (t - WINDOW, t], of which refreshed by t)."""
    sel = tr.flow_port[tr.pkt_fid] == port
    t, f = tr.pkt_t[sel], tr.pkt_fid[sel]
    order = np.lexsort((t, f))
    t, f = t[order], f[order]
    seen, ref = np.zeros(DUR + 2), np.zeros(DUR + 2)
    start = np.flatnonzero(np.r_[True, f[1:] != f[:-1]])
    for a, b in zip(start, np.r_[start[1:], len(f)]):
        tt = t[a:b]
        gap = np.diff(tt)
        hit = np.flatnonzero((gap >= G_MIN) & (gap < IDLE))
        first_ref = np.ceil(tt[hit[0] + 1]) if len(hit) else np.inf
        secs = np.unique(np.ceil(tt).astype(int))
        # Seen at t when it has a packet in (t - WINDOW, t]: the union of [s, s + WINDOW) over its seconds.
        brk = np.flatnonzero(np.diff(secs) >= WINDOW)
        for lo, hi in zip(secs[np.r_[0, brk + 1]], secs[np.r_[brk, len(secs) - 1]] + int(WINDOW)):
            lo, hi = min(lo, DUR + 1), min(hi, DUR + 1)
            seen[lo] += 1
            seen[hi] -= 1
            r = max(lo, int(first_ref)) if np.isfinite(first_ref) else hi
            if r < hi:
                ref[r] += 1
                ref[hi] -= 1
    return np.cumsum(seen)[:DUR + 1], np.cumsum(ref)[:DUR + 1]


def crowd_windows(tr):
    fids, idx = np.unique(tr.pkt_fid, return_index=True)      # packets are sorted by time
    st = np.sort(tr.pkt_t[idx][tr.flow_kind[fids] == KIND_CODE["flash"]])
    out = []
    for x in st:
        if out and x - out[-1][1] <= 5:
            out[-1][1] = x
        else:
            out.append([x, x])
    return out


def refresh_stats(tr, flows):
    """For each flow id: time from its first packet to its first refresh (inf if none within
    REFRESH_BY s). A refresh is a packet in a poll that follows >= IDLE_POLLS polls without packets of
    that flow, less than IDLE s after the flow's previous packet."""
    sel = np.isin(tr.pkt_fid, flows)
    t, f = tr.pkt_t[sel], tr.pkt_fid[sel]
    order = np.lexsort((t, f))
    t, f = t[order], f[order]
    out = {}
    start = np.flatnonzero(np.r_[True, f[1:] != f[:-1]])
    end = np.r_[start[1:], len(f)]
    for a, b in zip(start, end):
        tt = t[a:b]
        polls = np.unique(np.floor(tt))
        first = tt[0]
        hit = np.inf
        for p0, p1 in zip(polls[:-1], polls[1:]):
            if p1 - first > REFRESH_BY:
                break
            if p1 - p0 - 1 >= IDLE_POLLS and p1 - p0 < IDLE:
                hit = p1 - np.floor(first)
                break
        out[int(f[a])] = hit
    return out


def summarize(label, tr, flows):
    st = refresh_stats(tr, flows)
    v = np.array(list(st.values()))
    ok = np.isfinite(v)
    med = f"{np.median(v[ok]):.0f}" if ok.any() else "–"
    return f"| {label} | {len(v):,} | {100 * ok.mean():.1f} | {med} |"


def main():
    os.makedirs(OUT, exist_ok=True)
    L = ["# Refresh signal: flash crowds against low-rate attacks (offline, exploratory)", "",
         f"Schedules as sent on the testbed (T1B, benign scale 0.5). A flow is refreshed when it sends after "
         f">= {IDLE_POLLS} idle polls and within the {IDLE:.0f} s idle timeout; counted in its first "
         f"{REFRESH_BY:.0f} s.", "",
         "| Flows | Number | Refreshed (%) | Median time to first refresh (s) |", "|---|---|---|---|"]
    tr = schedule(None, 4187, crowd=2)
    crowd = np.flatnonzero(tr.flow_kind == KIND_CODE["flash"])
    benign = np.flatnonzero((tr.flow_kind != KIND_CODE["flash"]) & (tr.flow_owner < 0))
    L.append(summarize("Flash crowd F2 (seed 4187)", tr, crowd))
    L.append(summarize("Benign replay T1B (seed 4187)", tr, benign))
    for i in range(4):
        L.append(summarize(f"Benign replay, host {i + 1}", tr, benign[tr.flow_port[benign] == i]))
    for v in ATTACKS:
        tr = schedule(v, 4160)
        att = np.flatnonzero(tr.flow_owner >= 0)
        L.append(summarize(f"Attack {NAME[v]} (seed 4160)", tr, att))
        print(v, flush=True)
    # Gate G0 (docs/crowdguard_prereg.md, section 3).
    L += ["", "## Gate G0 (refresh share per host, 30 s window)", "",
          "| Host | Seconds checked | Share: smallest | largest | Rule | Result |", "|---|---|---|---|---|---|"]
    ok = True
    tr = schedule(None, 4187, crowd=2, one_host=True)
    seen, ref = host_share(tr, CROWD_HOST)
    ts = sorted({int(x) for a, b in crowd_windows(tr) for x in range(int(np.floor(a)), int(np.ceil(b)) + 11)
                 if x <= DUR and seen[x] > 0})
    sh = ref[ts] / seen[ts]
    p = sh.max() <= 0.3
    ok &= p
    L.append(f"| Crowd host d1h3, F2H seed 4187, crowds and 10 s after | {len(ts)} | {sh.min():.2f} | "
             f"{sh.max():.2f} | largest <= 0.3 | {'pass' if p else 'fail'} |")
    for v in ATTACKS:
        tr = schedule(v, 4160)
        for port in sorted(set(tr.flow_port[tr.flow_owner >= 0].tolist())):
            seen, ref = host_share(tr, port)
            ts = [x for x in range(70, DUR + 1) if seen[x] > 0]
            sh = ref[ts] / seen[ts]
            p = sh.min() >= 0.7
            ok &= p
            L.append(f"| {NAME[v]} attacker on port {port}, seed 4160, 70-300 s | {len(ts)} | {sh.min():.2f} | "
                     f"{sh.max():.2f} | smallest >= 0.7 | {'pass' if p else 'fail'} |")
        print(v, "G0", flush=True)
    L += ["", f"G0: {'pass' if ok else 'fail'}"]
    open(f"{OUT}/report.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
