"""Trace-driven benign traffic (real pcaps replayed into the simulator).

The related work replays IMC-10 university data-centre traces or bigFlows.pcap
with tcpreplay as background traffic (docs/experiments_from_related_work.md,
E2). A trace domain replays one such trace, converted once with
`python -m loftbench.pcapflows`, at a fixed total packet rate: trace time is
stretched (or compressed) by native_rate / rate_pps, the same effect as
tcpreplay --pps. Each seed starts the replay at a different offset, wrapping
around the end of the trace, so seeds give different but realistic traffic and
the same seed always gives the same benign traffic (paired comparisons).

Trace files are not in git. Set LOFT_TRACE_DIR, or put them in
loft_project/traces/ (see docs/traces.md).
"""
import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

TRACE_DIR = os.environ.get("LOFT_TRACE_DIR",
                           os.path.join(os.path.dirname(os.path.dirname(__file__)), "traces"))


@dataclass(frozen=True)
class TraceProfile:
    name: str
    file: str                  # .npz written by loftbench.pcapflows, relative to TRACE_DIR
    rate_pps: float            # total benign replay rate
    anchor: str = "src"        # which address ties a flow to a user host (ingress port):
                               # "private" = the RFC 1918 endpoint, else the source
    window: tuple = (0.0, 1.0)  # fraction of the capture's span replayed (docs/v5_plan.md)


TRACE_DOMAINS = {
    # DMS-BTT: bigFlows.pcap replayed by 4 user hosts at 300 pps each.
    "T1": TraceProfile("T1-bigflows", "bigflows.npz", 1200.0, anchor="private"),
    # FTOP: IMC-10 univ2 replayed at 1,000 pps (light: about 6 new flows/s).
    "T2": TraceProfile("T2-univ2", "univ2.npz", 1000.0),
    # The same univ2 window at its native rate (about 9,000 pps, 52 new flows/s).
    "T3": TraceProfile("T3-univ2-native", "univ2.npz", 9000.0),
    # The clean split of bigFlows (docs/v5_plan.md): every T1 model and threshold is trained or
    # calibrated on the first 40 % of the span (T1A); the testbed test replays only the rest
    # (T1B). 40 %: the split that leaves both parts one full replay pass (T1A 339k packets, 283 s
    # at 1,200 pps for the 240 s training runs; T1B 206k packets, 343 s at the testbed's 600 pps).
    "T1A": TraceProfile("T1A-bigflows-first-40pct", "bigflows.npz", 1200.0, anchor="private",
                        window=(0.0, 0.4)),
    "T1B": TraceProfile("T1B-bigflows-last-60pct", "bigflows.npz", 1200.0, anchor="private",
                        window=(0.4, 1.0)),
    # Real-traffic federated training (docs/realfl_plan.md): three univ2 parts, each the first
    # 3,000,000 packets of one capture file, replayed at its own captured rate.
    "U1": TraceProfile("U1-univ2-pt0", "univ2_pt0.npz", 11178.0),
    "U2": TraceProfile("U2-univ2-pt3", "univ2_pt3.npz", 10226.0),
    "UH": TraceProfile("UH-univ2-pt6", "univ2_pt6.npz", 9246.0),
    # T1B at the testbed's 600 pps (one replay pass is 343 s; at 1,200 pps it is 172 s).
    "T1Bt": TraceProfile("T1B-bigflows-last-60pct-600pps", "bigflows.npz", 600.0, anchor="private",
                         window=(0.4, 1.0)),
    # The univ2 parts on the testbed at FTOP's 1,000 pps (docs/testbed_training_plan.md).
    "U1t": TraceProfile("U1-univ2-pt0-1000pps", "univ2_pt0.npz", 1000.0),
    "U2t": TraceProfile("U2-univ2-pt3-1000pps", "univ2_pt3.npz", 1000.0),
    "UHt": TraceProfile("UH-univ2-pt6-1000pps", "univ2_pt6.npz", 1000.0),
}
# After D1-D3, for attacker address ranges; T1A and T1B are T1's network (same hosts, same
# attacker addresses), only the replayed part of the capture differs.
TRACE_DOMAIN_IDX = {"T1": 3, "T2": 4, "T3": 5, "T1A": 3, "T1B": 3, "U1": 6, "U2": 7, "UH": 8, "T1Bt": 3,
                    "U1t": 6, "U2t": 7, "UHt": 8}


@lru_cache(maxsize=4)
def load(file):
    path = file if os.path.isabs(file) else os.path.join(TRACE_DIR, file)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: convert the pcap with loftbench.pcapflows "
                                f"(see docs/traces.md)")
    z = np.load(path)
    tr = {k: z[k] for k in ("pkt_t", "pkt_fid", "pkt_size", "flow_src", "flow_dst")}
    return longest_segment(tr)


MAX_GAP_S = 10.0


def longest_segment(tr, max_gap=MAX_GAP_S):
    """Keep the longest stretch of the capture with no silence longer than max_gap.

    Capture artefacts (the univ2 window starts with one packet followed by 51.7 s of
    silence) would otherwise become minutes of empty replay at low rates. Flow ids are
    renumbered; times restart at 0."""
    t = tr["pkt_t"]
    cut = np.flatnonzero(np.diff(t) > max_gap) + 1
    if len(cut) == 0:
        return tr
    edges = np.r_[0, cut, len(t)]
    k = int(np.argmax(np.diff(edges)))
    a, b = edges[k], edges[k + 1]
    used, fid = np.unique(tr["pkt_fid"][a:b], return_inverse=True)
    return dict(pkt_t=t[a:b] - t[a], pkt_fid=fid.astype(np.int64), pkt_size=tr["pkt_size"][a:b],
                flow_src=tr["flow_src"][used], flow_dst=tr["flow_dst"][used])


def is_private(ip):
    ip = np.asarray(ip, np.int64)
    return (((ip >> 24) == 10) | ((ip >> 20) == (172 << 4 | 1)) | ((ip >> 16) == (192 << 8 | 168)))


def anchors(tr, mode):
    """Per-flow user-host address: a client's flows in both directions share it,
    as when a host replays the trace with tcpreplay."""
    src, dst = tr["flow_src"], tr["flow_dst"]
    if mode == "private":
        return np.where(is_private(src) | ~is_private(dst), src, dst)
    return src


def window(tr, lo, hi):
    """The part of a converted trace between fractions lo and hi of its span. A flow belongs to
    the part holding its first packet; its packets outside that part are dropped, so no flow
    appears in two parts. Times restart at 0; flow ids are kept."""
    if (lo, hi) == (0.0, 1.0):
        return tr
    t = tr["pkt_t"]
    span = float(t[-1]) + 1e-3
    a, b = lo * span, hi * span
    first = np.full(len(tr["flow_src"]), np.inf)
    np.minimum.at(first, tr["pkt_fid"], t)
    f_in = (first >= a) & (first < b)
    keep = (t >= a) & (t < b) & f_in[tr["pkt_fid"]]
    out = dict(tr)
    out["pkt_t"] = t[keep] - a
    out["pkt_fid"], out["pkt_size"] = tr["pkt_fid"][keep], tr["pkt_size"][keep]
    return out


def replay(tr, duration, rate_pps, rng, anchor="src"):
    """Window of a converted trace: benign packets (t, fid, size) and per flow
    (source address, anchor address)."""
    t0, fid0, size0, src0 = tr["pkt_t"], tr["pkt_fid"], tr["pkt_size"], tr["flow_src"]
    anc0 = anchors(tr, anchor) if "flow_dst" in tr else src0
    span = float(t0[-1]) + 1e-3
    stretch = (len(t0) / span) / rate_pps
    S = span * stretch                              # replayed length of one pass
    if duration > S:
        raise ValueError(f"episode of {duration} s exceeds one replay pass ({S:.0f} s)")
    off = rng.uniform(0, S)
    t = t0 * stretch - off
    # Packets of the current pass after the offset, then the next pass (fresh flows).
    a = t >= 0
    b = (t + S) < duration
    ts = np.concatenate([t[a], t[b] + S])
    fl = np.concatenate([fid0[a], fid0[b] + len(src0)])
    sz = np.concatenate([size0[a], size0[b]])
    keep = ts < duration
    ts, fl, sz = ts[keep], fl[keep], sz[keep]
    used, fid = np.unique(fl, return_inverse=True)
    src = np.concatenate([src0, src0])[used]
    anc = np.concatenate([anc0, anc0])[used]
    return ts, fid.astype(np.int64), sz.astype(np.int64), src.astype(np.int64), anc.astype(np.int64)


def generate_trace_benign(profile: TraceProfile, duration, rng):
    """Like traffic.generate_benign, (t, fid, size, srcs, kind_code), plus anchors."""
    from .traffic import TRACE_KIND
    t, fid, size, src, anc = replay(window(load(profile.file), *profile.window), duration,
                                    profile.rate_pps, rng, profile.anchor)
    order = np.argsort(t, kind="stable")
    return (t[order], fid[order], size[order], src, np.full(len(src), TRACE_KIND, np.int8), anc)
