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


TRACE_DOMAINS = {
    # DMS-BTT: bigFlows.pcap replayed by 4 user hosts at 300 pps each.
    "T1": TraceProfile("T1-bigflows", "bigflows.npz", 1200.0, anchor="private"),
    # FTOP: IMC-10 univ2 replayed at 1,000 pps (light: about 6 new flows/s).
    "T2": TraceProfile("T2-univ2", "univ2.npz", 1000.0),
    # The same univ2 window at its native rate (about 9,000 pps, 52 new flows/s).
    "T3": TraceProfile("T3-univ2-native", "univ2.npz", 9000.0),
}
TRACE_DOMAIN_IDX = {"T1": 3, "T2": 4, "T3": 5}  # after D1-D3, for attacker address ranges


@lru_cache(maxsize=4)
def load(file):
    path = file if os.path.isabs(file) else os.path.join(TRACE_DIR, file)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: convert the pcap with loftbench.pcapflows "
                                f"(see docs/traces.md)")
    z = np.load(path)
    return {k: z[k] for k in ("pkt_t", "pkt_fid", "pkt_size", "flow_src", "flow_dst")}


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
    t, fid, size, src, anc = replay(load(profile.file), duration, profile.rate_pps, rng,
                                    profile.anchor)
    order = np.argsort(t, kind="stable")
    return (t[order], fid[order], size[order], src, np.full(len(src), TRACE_KIND, np.int8), anc)
