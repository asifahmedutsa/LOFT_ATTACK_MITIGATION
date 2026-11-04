"""Controller-side causal feature extraction from OpenFlow flow statistics.

One extractor serves every flow regardless of its (hidden) label. Inputs are
only what an OpenFlow 1.3 controller can see: per-entry packet_count,
byte_count, duration and match fields (source address), plus the controller's
own history of previous polls and its own install log.
"""
import numpy as np

FEATURE_NAMES = [
    "log_pkts", "log_bytes", "log_dur", "mean_size", "log_rate", "log_pit",
    "log_dpkts", "idle_polls", "active_ratio", "gap_cv", "gap_mean",
    "src_entries", "src_new", "src_small_frac",
    "occupancy", "install_rate", "table_apit",
]
FLOW_FEATURES = FEATURE_NAMES[:11]
SOURCE_FEATURES = FEATURE_NAMES[11:14]
CONTEXT_FEATURES = FEATURE_NAMES[14:]
DMS_FLOW_FEATURES = ["Numb", "PIT", "Sizep"]
DMS_STATE_FEATURES = ["FN", "APIT"]


class FeatureTracker:
    def __init__(self, n_flows, flow_src, capacity, poll_interval):
        self.src = flow_src
        self.capacity = capacity
        self.poll = poll_interval
        self.seen_install = np.full(n_flows, -1.0)
        self.prev_pkts = np.zeros(n_flows, np.int64)
        self.polls = np.zeros(n_flows, np.int32)
        self.active = np.zeros(n_flows, np.int32)
        self.last_change = np.zeros(n_flows)
        self.gap_n = np.zeros(n_flows, np.int32)
        self.gap_mean = np.zeros(n_flows)
        self.gap_m2 = np.zeros(n_flows)
        self.install_hist = []  # installs per poll interval

    def observe(self, t, fids, pkts, bytes_, install_t, installs_since_last):
        """Update history with a stats reply and return feature matrices."""
        self.install_hist.append(installs_since_last)
        new = self.seen_install[fids] != install_t
        if new.any():
            nf = fids[new]
            self.seen_install[nf] = install_t[new]
            self.prev_pkts[nf] = 0
            self.polls[nf] = 0
            self.active[nf] = 0
            self.last_change[nf] = t
            self.gap_n[nf] = 0
            self.gap_mean[nf] = 0
            self.gap_m2[nf] = 0
        dp = pkts - self.prev_pkts[fids]
        self.prev_pkts[fids] = pkts
        act = dp > 0
        self.polls[fids] += 1
        self.active[fids] += act
        # Welford update of the gaps between polls with counter activity.
        upd = act & ~new
        if upd.any():
            uf = fids[upd]
            gap = t - self.last_change[uf]
            self.gap_n[uf] += 1
            d = gap - self.gap_mean[uf]
            self.gap_mean[uf] += d / self.gap_n[uf]
            self.gap_m2[uf] += d * (gap - self.gap_mean[uf])
        self.last_change[fids[act]] = t

        dur = np.maximum(t - install_t, 1e-3)
        pk = np.maximum(pkts, 1).astype(float)
        gn = self.gap_n[fids]
        gm = self.gap_mean[fids]
        gstd = np.sqrt(np.divide(self.gap_m2[fids], np.maximum(gn - 1, 1)))
        gap_cv = np.where(gn >= 2, gstd / np.maximum(gm, 1e-6), 0.0)

        src = self.src[fids]
        _, inv, cnt = np.unique(src, return_inverse=True, return_counts=True)
        recent = (t - install_t) <= 10.0
        small = pkts <= 3
        src_new = np.bincount(inv, weights=recent)[inv]
        src_small = np.bincount(inv, weights=small)[inv] / cnt[inv]

        n = len(fids)
        occ = n / self.capacity
        rate = sum(self.install_hist[-5:]) / (5 * self.poll) / self.capacity * 10
        pit = dur / pk
        apit = float(pit.mean()) if n else 0.0

        X = np.column_stack([
            np.log1p(pkts), np.log1p(bytes_), np.log1p(dur),
            bytes_ / pk / 1500.0, np.log1p(pkts / np.maximum(dur, 1.0)),
            np.log1p(pit), np.log1p(np.maximum(dp, 0)),
            np.minimum((t - self.last_change[fids]) / self.poll, 10) / 10.0,
            self.active[fids] / np.maximum(self.polls[fids], 1),
            np.minimum(gap_cv, 3.0), np.minimum(gm, 20.0) / 10.0,
            np.log1p(cnt[inv]), np.log1p(src_new), src_small,
            np.full(n, occ), np.full(n, rate), np.full(n, np.log1p(apit)),
        ]).astype(np.float32)
        dms = np.column_stack([bytes_.astype(float), pit, bytes_ / pk]).astype(np.float32)
        state = {"FN": n, "APIT": apit}
        return X, dms, state
