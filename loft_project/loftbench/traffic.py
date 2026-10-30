"""Packet-level traffic generation for one domain episode.

Benign and attack traffic come from independent random streams so that the
same (domain, seed) yields identical benign traffic under every attack variant
and every defense (paired comparisons). Ground-truth labels come from traffic
provenance, never from features.
"""
from dataclasses import dataclass

import numpy as np

from .config import FLOW_KINDS, AttackVariant, DomainProfile
from .trace import TraceProfile, generate_trace_benign

ATTACK_KIND = len(FLOW_KINDS)  # kind code for attack flows
TRACE_KIND = ATTACK_KIND + 1   # kind code for benign flows replayed from a pcap trace
KIND_CODE = {k: i for i, k in enumerate(FLOW_KINDS)}


@dataclass
class Traffic:
    pkt_t: np.ndarray        # float64, sorted
    pkt_fid: np.ndarray      # int32
    pkt_size: np.ndarray     # int32 bytes
    flow_attack: np.ndarray  # bool per flow id
    flow_src: np.ndarray     # int64 source address per flow id
    flow_kind: np.ndarray    # int8 per flow id
    attack_active: list      # [(t_on, t_off)] intervals with attack refreshes
    flow_owner: np.ndarray = None  # int8 per flow id: -1 benign, else attacker index
    flow_port: np.ndarray = None   # int16 ingress port per flow id (see ports.py)
    flow_anchor: np.ndarray = None  # int64 user-host address per flow (trace replay), else None

    @property
    def n_flows(self):
        return len(self.flow_attack)


def _rng(*keys):
    return np.random.default_rng([abs(hash_key(k)) for k in keys])


def hash_key(k):
    if isinstance(k, (int, np.integer)):
        return int(k)
    # Stable string hash (Python's hash() is salted per process).
    h = 1469598103934665603
    for ch in str(k).encode():
        h = ((h ^ ch) * 1099511628211) % (1 << 61)
    return h


def _group_times(starts, n, iat):
    """Packet timestamps: each flow starts at starts[i] and accumulates iat."""
    first = np.concatenate(([0], np.cumsum(n)[:-1]))
    iat = iat.copy()
    iat[first] = 0.0
    c = np.cumsum(iat)
    return np.repeat(starts, n) + c - np.repeat(c[first], n)


def _sizes(kind, m, rng):
    if kind in ("dns",):
        return rng.integers(60, 180, m)
    if kind in ("mice", "flash"):
        small = rng.random(m) < 0.4
        return np.where(small, rng.integers(64, 100, m), rng.integers(300, 1400, m))
    if kind == "elephant":
        return np.where(rng.random(m) < 0.9, rng.integers(1400, 1500, m), 64)
    if kind == "periodic":
        return rng.integers(60, 300, m)
    if kind == "interactive":
        return rng.integers(80, 250, m)
    raise ValueError(kind)


def benign_size_sampler(m, rng):
    """Packet sizes drawn from the pooled benign mixture (used by mimicry)."""
    kinds = rng.choice(["dns", "mice", "periodic", "interactive"], size=m)
    out = np.empty(m, dtype=np.int64)
    for k in np.unique(kinds):
        sel = kinds == k
        out[sel] = _sizes(k, int(sel.sum()), rng)
    return out


def generate_benign(profile: DomainProfile, duration: float, domain_idx: int, rng):
    kinds_l = list(profile.mix)
    p = np.array([profile.mix[k] for k in kinds_l], dtype=float)
    p /= p.sum()
    n_f = rng.poisson(profile.new_flow_rate * duration)
    starts = np.sort(rng.uniform(0, duration, n_f))
    kind_idx = rng.choice(len(kinds_l), size=n_f, p=p)
    kinds = np.array(kinds_l, dtype=object)[kind_idx]

    ranks = np.arange(1, profile.n_clients + 1)
    pz = ranks ** (-profile.zipf_a)
    pz /= pz.sum()
    srcs = (0x0A000000 + domain_idx * 65536 + rng.choice(profile.n_clients, n_f, p=pz)).astype(np.int64)

    # Benign flash crowds: many new short flows from many external sources.
    fl_starts, fl_srcs = [], []
    scale = duration / 300.0
    for _ in range(rng.poisson(profile.flash_events * scale) if profile.flash_events else 0):
        t0 = rng.uniform(20, max(21, duration - profile.flash_len - 5))
        m = rng.poisson(profile.flash_rate * profile.flash_len)
        fl_starts.append(np.sort(rng.uniform(t0, t0 + profile.flash_len, m)))
        fl_srcs.append(0xC0000000 + rng.integers(0, 1 << 20, m))
    if fl_starts:
        fs = np.concatenate(fl_starts)
        starts = np.concatenate([starts, fs])
        kinds = np.concatenate([kinds, np.array(["flash"] * len(fs), dtype=object)])
        srcs = np.concatenate([srcs, np.concatenate(fl_srcs).astype(np.int64)])

    n_total = len(starts)
    npk = np.zeros(n_total, dtype=np.int64)
    scale_iat = np.zeros(n_total)
    for k in np.unique(kinds):
        sel = kinds == k
        m = int(sel.sum())
        if k == "dns":
            npk[sel] = 1 + (rng.random(m) < 0.3)
            scale_iat[sel] = 0.02
        elif k in ("mice", "flash"):
            npk[sel] = rng.geometric(1 / 8 if k == "mice" else 1 / 5, m)
            scale_iat[sel] = 0.05
        elif k == "elephant":
            a, xm = profile.elephant_pareto
            npk[sel] = np.minimum(5000, (xm * (1 + rng.pareto(a, m))).astype(np.int64))
            scale_iat[sel] = 0.01
        elif k == "periodic":
            period = rng.uniform(*profile.periodic_period, m)
            dur = rng.uniform(*profile.periodic_duration, m)
            npk[sel] = np.maximum(2, (dur / period).astype(np.int64))
            scale_iat[sel] = period
        elif k == "interactive":
            npk[sel] = rng.geometric(1 / 30, m)
            scale_iat[sel] = 1.0

    rep_kind = np.repeat(kinds, npk)
    rep_scale = np.repeat(scale_iat, npk)
    periodic_mask = rep_kind == "periodic"
    iat = rng.exponential(1.0, len(rep_scale)) * rep_scale
    # Periodic flows: near-constant period with 5% jitter.
    iat[periodic_mask] = rep_scale[periodic_mask] * np.clip(
        1 + 0.05 * rng.standard_normal(int(periodic_mask.sum())), 0.8, 1.2)
    t = _group_times(starts, npk, iat)
    size = np.empty(len(t), dtype=np.int64)
    for k in np.unique(kinds):
        sel = rep_kind == k
        size[sel] = _sizes(k, int(sel.sum()), rng)
    fid = np.repeat(np.arange(n_total), npk)
    kind_code = np.array([KIND_CODE[k] for k in kinds], dtype=np.int8)
    return t, fid, size, srcs, kind_code


def generate_attack(variant: AttackVariant, start: float, duration: float,
                    domain_idx: int, fid_offset: int, rng, owner_out=None):
    """DMS-BTT LFTO recurrence with optional mimicry, spoofing and pulsing.

    If owner_out is a list, the attacker index of every new flow is appended to
    it (no random draws, so traffic is unchanged)."""
    ts, fids, sizes, flow_src = [], [], [], []
    active_intervals = []
    next_fid = fid_offset
    for a in range(variant.n_attackers):
        host_ip = 0x0A00FF00 + domain_idx * 16 + a
        pool_base = 0x0AFE0000 + domain_idx * 4096 + a * 256
        t = start + rng.uniform(0, variant.t1_range[1])
        live = []          # flow ids currently refreshed by this attacker
        n_target = 0
        phase_end = t + variant.pulse_on if variant.pulse_on > 0 else np.inf
        on_since = t
        while t < duration:
            if t >= phase_end:
                # Pulse off: stop refreshing; entries age out, then restart
                # with fresh 5-tuples.
                active_intervals.append((on_since, t))
                t += variant.pulse_off
                live, n_target = [], 0
                on_since = t
                phase_end = t + variant.pulse_on
                continue
            n_target = min(variant.max_flows, n_target + variant.step)
            n_new = n_target - len(live)
            if n_new > 0:
                new = list(range(next_fid, next_fid + n_new))
                next_fid += n_new
                if variant.src_mode == "host":
                    flow_src.extend([host_ip] * n_new)
                elif variant.src_mode == "pool":
                    flow_src.extend((pool_base + rng.integers(0, 256, n_new)).tolist())
                else:
                    flow_src.extend(rng.integers(0x01000000, 0xDF000000, n_new).tolist())
                live.extend(new)
                if owner_out is not None:
                    owner_out.extend([a] * n_new)
            lo, hi = variant.pkts_per_refresh
            reps = rng.integers(lo, hi + 1, len(live))
            f = np.repeat(np.array(live), reps)
            order = rng.permutation(len(f))
            f = f[order]
            tt = t + np.arange(len(f)) / variant.burst_pps
            if variant.size_mode == "fixed":
                sz = np.full(len(f), 64)
            else:
                sz = benign_size_sampler(len(f), rng)
            ts.append(tt)
            fids.append(f)
            sizes.append(sz)
            t += rng.uniform(*variant.t1_range)
        active_intervals.append((on_since, min(t, duration)))
    if ts:
        t = np.concatenate(ts)
        keep = t < duration
        return (t[keep], np.concatenate(fids)[keep], np.concatenate(sizes)[keep],
                np.array(flow_src, dtype=np.int64), active_intervals)
    return (np.zeros(0), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64),
            np.zeros(0, dtype=np.int64), [])


def build_traffic(profile, domain_idx: int, variant, seed: int,
                  duration: float, attack_start: float) -> Traffic:
    rb = _rng("benign", profile.name, seed)
    banc = None
    if isinstance(profile, TraceProfile):
        bt, bf, bs, bsrc, bkind, banc = generate_trace_benign(profile, duration, rb)
    else:
        bt, bf, bs, bsrc, bkind = generate_benign(profile, duration, domain_idx, rb)
    n_b = len(bsrc)
    owner = []
    if variant is not None:
        ra = _rng("attack", profile.name, variant.name, seed)
        at, af, asz, asrc, intervals = generate_attack(
            variant, attack_start, duration, domain_idx, n_b, ra, owner_out=owner)
    else:
        at, af, asz, asrc, intervals = (np.zeros(0), np.zeros(0, dtype=np.int64),
                                        np.zeros(0, dtype=np.int64),
                                        np.zeros(0, dtype=np.int64), [])
    t = np.concatenate([bt, at])
    fid = np.concatenate([bf, af]).astype(np.int32)
    size = np.concatenate([bs, asz]).astype(np.int32)
    keep = t < duration
    t, fid, size = t[keep], fid[keep], size[keep]
    order = np.argsort(t, kind="stable")
    flow_attack = np.concatenate([np.zeros(n_b, bool), np.ones(len(asrc), bool)])
    flow_kind = np.concatenate([bkind, np.full(len(asrc), ATTACK_KIND, np.int8)])
    flow_owner = np.concatenate([np.full(n_b, -1, np.int8), np.array(owner, np.int8)])
    flow_src = np.concatenate([bsrc, asrc])
    flow_anchor = None if banc is None else np.concatenate([banc, asrc])
    return Traffic(t[order], fid[order], size[order], flow_attack, flow_src, flow_kind,
                   intervals, flow_owner, flow_anchor=flow_anchor)
