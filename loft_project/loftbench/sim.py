"""Discrete-time bounded flow-table switch with a polling controller.

Per tick (cfg.dt): expire idle entries, match packets against installed
entries (updating counters), send table misses to the controller as
Packet-In and admit new entries while capacity remains; rejected admissions
raise table-full errors and the packet takes the controller slow path.
Every cfg.poll_interval the controller reads flow statistics and the defense
may delete entries or demote flows (delete now, reinstall with a short idle
timeout on the next Packet-In).
"""
import time
from dataclasses import dataclass, field

import numpy as np

from .config import SimConfig
from .features import FeatureTracker


class Defense:
    """No defense. Subclasses override hooks."""
    name = "none"
    needs_features = False
    evict_on_full = None   # optional callable(n_needed, installed_fids, last_seen, idle_to, now)
    admit_filter = None    # optional callable(fids, now) -> bool mask of flows allowed an entry

    def reset(self, ctx):
        pass

    def admit_timeouts(self, fids, now, default):
        return np.full(len(fids), default)

    def on_poll(self, t, obs):
        """Return (delete_fids, demote_fids)."""
        return None, None


@dataclass
class EpisodeResult:
    summary: dict
    timeseries: list = field(default_factory=list)
    samples: list = field(default_factory=list)


def run_episode(traffic, cfg: SimConfig, defense: Defense = None, collect=None,
                collect_frac=0.05, collect_rng=None, record_ts=True):
    defense = defense or Defense()
    n = traffic.n_flows
    cap = cfg.capacity - cfg.infra_rules
    installed = np.zeros(n, bool)
    install_t = np.zeros(n)
    last_seen = np.zeros(n)
    idle_to = np.full(n, cfg.idle_timeout)
    pkts = np.zeros(n, np.int64)
    byts = np.zeros(n, np.int64)
    count = 0
    is_att = traffic.flow_attack

    tracker = FeatureTracker(n, traffic.flow_src, cfg.capacity, cfg.poll_interval)
    defense.reset({"cfg": cfg, "n_flows": n, "flow_src": traffic.flow_src,
                   "flow_port": traffic.flow_port})

    ticks = int(round(cfg.duration / cfg.dt))
    bounds = np.searchsorted(traffic.pkt_t, np.arange(ticks + 1) * cfg.dt)
    poll_every = int(round(cfg.poll_interval / cfg.dt))

    # Accounting
    benign_flow_rejected = np.zeros(n, bool)
    benign_flow_seen = np.zeros(n, bool)
    benign_flow_evicted = np.zeros(n, bool)
    # A removed benign entry harms its flow only if the flow sends again before
    # the entry would have idled out on its own; otherwise the entry was stale.
    evict_pending = np.zeros(n, bool)
    evict_deadline = np.zeros(n)
    benign_flow_active_harm = np.zeros(n, bool)
    benign_flow_blocked = np.zeros(n, bool)

    def mark_removed(arr):
        b = arr[~is_att[arr]]
        benign_flow_evicted[b] = True
        evict_pending[b] = True
        evict_deadline[b] = last_seen[b] + idle_to[b]
    tot = dict(packet_in=0, table_full=0, benign_pkts=0, benign_rejected_pkts=0,
               benign_packet_in=0, attack_pkts=0, deletes=0, demotes=0,
               benign_deletes=0, benign_demotes=0, attack_deletes=0, attack_demotes=0,
               installs=0, evictions=0, benign_evictions=0, benign_evict_repackets=0,
               blocked_pkts=0, benign_blocked_pkts=0)
    full_ticks = 0
    first_full = None
    full_ticks_post = 0
    decision_time = []
    ts = []
    installs_interval = 0
    sec_pi = sec_tf = sec_brej = sec_bp = 0
    att_occ_sum = att_occ_post_sum = 0.0
    att_occ_max = 0.0
    n_polls = n_polls_post = 0
    ben_occ_sum = 0.0

    for k in range(ticks):
        now = k * cfg.dt
        # 1. idle-timeout expiry
        idx = np.flatnonzero(installed)
        if len(idx):
            exp = idx[last_seen[idx] + idle_to[idx] <= now]
            if len(exp):
                installed[exp] = False
                count -= len(exp)
        # 2. packets in this tick
        lo, hi = bounds[k], bounds[k + 1]
        if hi > lo:
            pf = traffic.pkt_fid[lo:hi]
            pt = traffic.pkt_t[lo:hi]
            ps = traffic.pkt_size[lo:hi]
            pat = is_att[pf]
            tot["attack_pkts"] += int(pat.sum())
            tot["benign_pkts"] += int((~pat).sum())
            sec_bp += int((~pat).sum())
            benign_flow_seen[pf[~pat]] = True
            inst = installed[pf]
            if inst.any():
                f = pf[inst]
                np.add.at(pkts, f, 1)
                np.add.at(byts, f, ps[inst])
                np.maximum.at(last_seen, f, pt[inst])
            if (~inst).any():
                miss = ~inst
                mf, mt, ms = pf[miss], pt[miss], ps[miss]
                u, first = np.unique(mf, return_index=True)
                order = np.argsort(first, kind="stable")
                u, first = u[order], first[order]
                pend = evict_pending[u]
                if pend.any():
                    pu = u[pend]
                    hit = mt[first[pend]] < evict_deadline[pu]
                    benign_flow_active_harm[pu[hit]] = True
                    tot["benign_evict_repackets"] += int(hit.sum())
                    evict_pending[pu] = False
                blocked_pk = None
                admit_filter = getattr(defense, "admit_filter", None)
                if admit_filter is not None:
                    # Controller blocklist: refused flows get no entry and their
                    # packets are dropped at the controller (no TABLE_FULL).
                    ok = admit_filter(u, now)
                    if not ok.all():
                        blk = u[~ok]
                        u, first = u[ok], first[ok]
                        blocked_pk = np.isin(mf, blk)
                        nb = int(blocked_pk.sum())
                        bb = blocked_pk & ~is_att[mf]
                        tot["packet_in"] += nb
                        sec_pi += nb
                        tot["blocked_pkts"] += nb
                        tot["benign_blocked_pkts"] += int(bb.sum())
                        tot["benign_packet_in"] += int(bb.sum())
                        benign_flow_blocked[mf[bb]] = True
                        benign_flow_rejected[mf[bb]] = True
                free = max(cap - count, 0)
                if len(u) > free and defense.evict_on_full is not None:
                    # Switch-side eviction (OVS overflow_policy=evict).
                    cand = np.flatnonzero(installed)
                    ev = defense.evict_on_full(len(u) - free, cand, last_seen, idle_to, now)
                    if len(ev):
                        installed[ev] = False
                        count -= len(ev)
                        tot["evictions"] += len(ev)
                        tot["benign_evictions"] += int((~is_att[ev]).sum())
                        mark_removed(ev)
                        free = max(cap - count, 0)
                adm, rej = u[:free], u[free:]
                if len(adm):
                    installed[adm] = True
                    install_t[adm] = mt[first[:free]]
                    idle_to[adm] = defense.admit_timeouts(adm, now, cfg.idle_timeout)
                    pkts[adm] = 0
                    byts[adm] = 0
                    count += len(adm)
                    installs_interval += len(adm)
                    tot["installs"] += len(adm)
                    # Packet-Out to OFPP_TABLE: the triggering packet and any
                    # later packets of this tick hit the new entry.
                    adm_mask = installed[mf]
                    np.add.at(pkts, mf[adm_mask], 1)
                    np.add.at(byts, mf[adm_mask], ms[adm_mask])
                    np.maximum.at(last_seen, mf[adm_mask], mt[adm_mask])
                # Packet-In: first packet of each admitted flow, every packet
                # of a rejected flow (each retried and refused with TABLE_FULL).
                rej_mask = ~installed[mf]
                if blocked_pk is not None:
                    rej_mask &= ~blocked_pk
                n_pi = len(adm) + int(rej_mask.sum())
                tot["packet_in"] += n_pi
                tot["table_full"] += int(rej_mask.sum())
                sec_pi += n_pi
                sec_tf += int(rej_mask.sum())
                ben_rej = rej_mask & ~is_att[mf]
                nbr = int(ben_rej.sum())
                tot["benign_rejected_pkts"] += nbr
                sec_brej += nbr
                benign_flow_rejected[mf[ben_rej]] = True
                tot["benign_packet_in"] += int((~is_att[adm]).sum()) + nbr
        if count >= cap:
            full_ticks += 1
            if now >= cfg.attack_start:
                full_ticks_post += 1
            if first_full is None:
                first_full = now

        # 3. controller poll
        if (k + 1) % poll_every == 0:
            t = (k + 1) * cfg.dt
            fids = np.flatnonzero(installed)
            t0 = time.perf_counter()
            obs = {"t": t, "fids": fids, "count": count, "capacity": cfg.capacity,
                   "table_full_last": sec_tf,
                   "pkts": pkts[fids], "bytes": byts[fids], "install_t": install_t[fids]}
            if defense.needs_features or collect is not None:
                X, dms, state = tracker.observe(t, fids, pkts[fids], byts[fids],
                                                install_t[fids], installs_interval)
                obs.update(X=X, dms=dms, state=state)
            installs_interval = 0
            dels, dems = defense.on_poll(t, obs)
            decision_time.append(time.perf_counter() - t0)
            for arr, kind in ((dels, "deletes"), (dems, "demotes")):
                if arr is not None and len(arr):
                    arr = np.unique(arr)
                    arr = arr[installed[arr]]
                    installed[arr] = False
                    count -= len(arr)
                    tot[kind] += len(arr)
                    na = int(is_att[arr].sum())
                    tot["attack_" + kind] += na
                    tot["benign_" + kind] += len(arr) - na
                    mark_removed(arr)
            n_att = int(is_att[fids].sum())
            att_occ = n_att / cfg.capacity
            att_occ_sum += att_occ
            att_occ_max = max(att_occ_max, att_occ)
            ben_occ_sum += (len(fids) - n_att) / cfg.capacity
            n_polls += 1
            if t > cfg.attack_start:
                att_occ_post_sum += att_occ
                n_polls_post += 1
            if collect is not None:
                collect(t, fids, obs, is_att[fids])
            if record_ts:
                ts.append(dict(t=t, occupancy=len(fids) / cfg.capacity,
                               attack_occ=att_occ, benign_entries=len(fids) - n_att,
                               packet_in=sec_pi, table_full=sec_tf,
                               benign_pkts=sec_bp, benign_rejected=sec_brej))
            sec_pi = sec_tf = sec_brej = sec_bp = 0

    nb_seen = int(benign_flow_seen.sum())
    summary = dict(
        benign_flows=nb_seen,
        benign_flows_rejected_frac=float(benign_flow_rejected.sum() / max(nb_seen, 1)),
        benign_pkt_reject_frac=tot["benign_rejected_pkts"] / max(tot["benign_pkts"], 1),
        benign_flows_evicted_frac=float(benign_flow_evicted.sum() / max(nb_seen, 1)),
        benign_flows_impacted_frac=float((benign_flow_evicted | benign_flow_rejected).sum()
                                         / max(nb_seen, 1)),
        # Service-level harm: refused an entry (slow path), or evicted while active.
        benign_flows_active_evicted_frac=float(benign_flow_active_harm.sum() / max(nb_seen, 1)),
        benign_flows_stale_evicted_frac=float((benign_flow_evicted & ~benign_flow_active_harm).sum()
                                              / max(nb_seen, 1)),
        benign_flows_blocked_frac=float(benign_flow_blocked.sum() / max(nb_seen, 1)),
        benign_flows_harmed_frac=float((benign_flow_active_harm | benign_flow_rejected).sum()
                                       / max(nb_seen, 1)),
        overflow_seconds=full_ticks * cfg.dt,
        overflow_seconds_post_attack=full_ticks_post * cfg.dt,
        first_overflow_s=first_full,
        avg_attack_occ=att_occ_sum / max(n_polls, 1),
        avg_attack_occ_post=att_occ_post_sum / max(n_polls_post, 1),
        max_attack_occ=att_occ_max,
        avg_benign_occ=ben_occ_sum / max(n_polls, 1),
        decision_ms_mean=1000 * float(np.mean(decision_time)),
        decision_ms_p99=1000 * float(np.percentile(decision_time, 99)),
        **tot,
    )
    return EpisodeResult(summary, ts)
