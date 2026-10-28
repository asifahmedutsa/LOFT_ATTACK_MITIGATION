"""Defense policies executed by the controller at every stats poll."""
import numpy as np

from .sim import Defense


def dms_transform(X, numb_mode="bytes"):
    """DMS-BTT flow features (Numb, PIT, Sizep). numb_mode="packets" replaces the
    byte count with the packet count (bytes / Sizep); the paper's definition must
    be checked against its Section 4."""
    if numb_mode == "bytes":
        return X
    X = X.copy()
    X[:, 0] = X[:, 0] / np.maximum(X[:, 2], 1e-6)
    return X


def _proba(model, X):
    p = model.predict_proba(X)
    return p[:, 1] if p.ndim == 2 else p


def _elephants(byts, pct=90):
    if len(byts) == 0:
        return np.zeros(0, bool)
    return byts >= np.percentile(byts, pct)


class OVSEvict(Defense):
    """Switch-side eviction on full table (OVS overflow_policy=evict):
    evict the entries closest to idle expiry. No controller logic."""
    name = "ovs-evict"

    def __init__(self):
        self.evict_on_full = self._evict

    @staticmethod
    def _evict(n_needed, cand, last_seen, idle_to, now):
        remaining = last_seen[cand] + idle_to[cand] - now
        k = min(n_needed, len(cand))
        return cand[np.argpartition(remaining, k - 1)[:k]] if k > 0 else cand[:0]


class ThresholdLRU(Defense):
    """Occupancy-triggered heuristic: above H1 delete the lowest-rate entries
    until occupancy falls below H2. No learning."""
    name = "threshold-lru"

    def __init__(self, h1=0.90, h2=0.75):
        self.h1, self.h2 = h1, h2

    def on_poll(self, t, obs):
        occ = obs["count"] / obs["capacity"]
        if occ < self.h1:
            return None, None
        n_del = obs["count"] - int(self.h2 * obs["capacity"])
        rate = obs["pkts"] / np.maximum(t - obs["install_t"], 1.0)
        return obs["fids"][np.argsort(rate, kind="stable")[:n_del]], None


class DMSBTT(Defense):
    """Reimplementation of DMS-BTT (two-level threshold defense).

    State detection: CatBoost on (FN, APIT) -> {normal, pre-overflow attack,
    overflow attack}. Malicious-flow identification: CatBoost on
    (Numb, PIT, Sizep). Mitigation: when an attack state is detected and
    occupancy >= H2, delete entries classified malicious; if occupancy is
    still >= H1, delete further entries in decreasing malicious probability
    until occupancy < H2. Elephant flows (top 10% bytes) are protected.

    Revision knobs (defaults reproduce the original reimplementation):
    p_thresh is the flow-classifier decision threshold; numb_mode selects the
    Numb definition; blocklist_s > 0 refuses re-admission of flows deleted as
    malicious for that many seconds (their packets are dropped at the controller).
    """
    name = "dms-btt"
    needs_features = True

    def __init__(self, state_model, flow_model, h1=0.90, h2=0.75, p_thresh=0.5,
                 numb_mode="bytes", blocklist_s=0.0):
        self.state_model, self.flow_model = state_model, flow_model
        self.h1, self.h2 = h1, h2
        self.p_thresh, self.numb_mode, self.blocklist_s = p_thresh, numb_mode, blocklist_s
        if blocklist_s > 0:
            self.admit_filter = self._admit

    def reset(self, ctx):
        self.blocked_until = np.zeros(ctx["n_flows"])

    def _admit(self, fids, now):
        return self.blocked_until[fids] <= now

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        if n == 0:
            return None, None
        st = int(np.ravel(self.state_model.predict(
            np.array([[obs["state"]["FN"], obs["state"]["APIT"]]])))[0])
        occ = n / cap
        if st == 0 or occ < self.h2:
            return None, None
        p = _proba(self.flow_model, dms_transform(obs["dms"], self.numb_mode))
        eleph = _elephants(obs["bytes"])
        dels = (p >= self.p_thresh) & ~eleph
        if self.blocklist_s > 0:
            self.blocked_until[obs["fids"][dels]] = t + self.blocklist_s
        n_after = n - int(dels.sum())
        if n_after / cap >= self.h1:
            extra = np.flatnonzero(~dels & ~eleph)
            extra = extra[np.argsort(-p[extra], kind="stable")]
            k = n_after - int(self.h2 * cap) + 1
            dels[extra[:k]] = True
        return obs["fids"][dels], None


class DualGuard(Defense):
    """Proposed controller policy (FL-DualGuard).

    Scores every entry with a (federated) detector and acts only under table
    pressure (occupancy >= rho):
      * soft action: entries scoring >= tau_soft are demoted: deleted now and
        re-installed with a short idle timeout on their next Packet-In. A
        benign false positive pays one extra Packet-In and stays forwardable;
        an LFTO flow refreshing every t1 > t_short loses most of its residency.
      * hard action: if occupancy is still >= h_crit, delete the highest-scoring
        non-elephant entries until occupancy <= target (overflow guard).
    tau_soft is calibrated per controller on local benign validation scores so
    that the empirical benign flag rate is <= the declared budget.
    """
    needs_features = True

    def __init__(self, model, tau_soft, name="dualguard", soft=True, hard=True,
                 rho=0.5, h_crit=0.90, target=0.80, t_short=1.0, feature_idx=None,
                 inputs="X", numb_mode="bytes", state_model=None):
        self.model, self.tau = model, tau_soft
        self.name = name
        self.soft, self.hard = soft, hard
        self.rho, self.h_crit, self.target, self.t_short = rho, h_crit, target, t_short
        self.feature_idx = feature_idx
        # inputs="dms" scores DMS-BTT's (Numb, PIT, Sizep) features instead of ours;
        # state_model (DMS-BTT state classifier) optionally gates all actions.
        self.inputs, self.numb_mode, self.state_model = inputs, numb_mode, state_model

    def reset(self, ctx):
        self.demoted = np.zeros(ctx["n_flows"], bool)

    def admit_timeouts(self, fids, now, default):
        return np.where(self.demoted[fids], self.t_short, default)

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        if n == 0 or n / cap < self.rho:
            return None, None
        if self.state_model is not None and int(np.ravel(self.state_model.predict(
                np.array([[obs["state"]["FN"], obs["state"]["APIT"]]])))[0]) == 0:
            return None, None
        if self.inputs == "dms":
            s = _proba(self.model, dms_transform(obs["dms"], self.numb_mode))
        else:
            X = obs["X"] if self.feature_idx is None else obs["X"][:, self.feature_idx]
            s = self.model.predict_proba(X)
        flag = s >= self.tau
        dems = obs["fids"][flag]
        if self.soft:
            self.demoted[dems] = True
        dels = None
        n_after = n - int(flag.sum())
        if self.hard and n_after / cap >= self.h_crit:
            eleph = _elephants(obs["bytes"])
            rest = np.flatnonzero(~flag & ~eleph)
            rest = rest[np.argsort(-s[rest], kind="stable")]
            k = n_after - int(self.target * cap)
            dels = obs["fids"][rest[:k]]
        return dels, dems


def weighted_level(demands, weights, target):
    """lam with sum(min(demands, weights * lam)) == target (inf if all fit)."""
    d, w = np.asarray(demands, float), np.asarray(weights, float)
    if np.isfinite(d).all() and d.sum() <= target:
        return np.inf
    lo, hi = 0.0, float(target) / max(w.min(), 1e-9)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if np.minimum(d, w * mid).sum() > target:
            hi = mid
        else:
            lo = mid
    return lo


def water_level(demands, target):
    """Max-min fair level L with sum(min(demands, L)) == target (inf if all fit).

    Demands may be inf (a port that is being refused has unknown demand)."""
    d = np.asarray(demands, float)
    if np.isfinite(d).all() and d.sum() <= target:
        return np.inf
    lo, hi = 0.0, float(target)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if np.minimum(d, mid).sum() > target:
            hi = mid
        else:
            lo = mid
    return lo


class PortGuard(Defense):
    """Per-ingress-port max-min fair share under table pressure (revision step 4).

    Wraps another defense (or none). Once occupancy reaches rho_q, enforcement
    stays on for hold_s seconds after the last such poll. While it is on, the
    table is held at target = q * capacity: every port gets a quota equal to the
    max-min fair level L, ports above L are trimmed to it (highest detector
    score first, or lowest packet rate when there is no detector), and new
    entries are admitted only while the port's count (at the last poll plus
    the controller's own installs since) is below L. A port that was refused
    since the last poll has unknown demand and is treated as unbounded. An
    honest port therefore keeps min(demand, q * capacity / n_ports) entries
    whatever the attacker's refresh rate, packet sizes or source IPs.

    mode sets how the inner defense runs while PortGuard is enforcing (revision
    step 4b): "full" always runs it on the whole table (step 4), "gated" pauses
    it, "scoped" runs it only on entries of ports above the fair level. order
    picks which entries a trimmed port loses first: "auto" (detector score if
    there is one, else lowest packet rate), "score" or "rate". share="weighted"
    replaces equal shares by weighted max-min fairness, each port weighted by its
    entry count averaged (time constant tau_s) over polls without table pressure;
    those demands fit in the table by construction, and a port that only grows
    under pressure earns little weight.
    """
    MODES = ("full", "gated", "scoped")

    def __init__(self, inner=None, rho_q=0.9, q=0.8, hold_s=30.0, name="portguard", mode="full",
                 order="auto", share="equal", tau_s=60.0):
        if (mode not in self.MODES or order not in ("auto", "score", "rate")
                or share not in ("equal", "weighted")):
            raise ValueError((mode, order, share))
        self.inner, self.rho_q, self.q, self.hold_s, self.name = inner, rho_q, q, hold_s, name
        self.mode, self.order, self.share, self.tau_s = mode, order, share, tau_s
        self.needs_features = bool(inner is not None and inner.needs_features)
        self._inner_admit = getattr(inner, "admit_filter", None)
        self.admit_filter = self._admit

    def reset(self, ctx):
        if self.inner is not None:
            self.inner.reset(ctx)
        self.port = ctx["flow_port"]
        if self.port is None:
            raise ValueError("PortGuard needs traffic.flow_port (see ports.assign_ports)")
        n_ports = int(self.port.max()) + 1
        self.quota = np.full(n_ports, np.inf)
        self.used = np.zeros(n_ports)        # entries at last poll + installs since
        self.refused = np.zeros(n_ports, bool)
        self.active_until = -np.inf
        self.base = np.zeros(n_ports)        # calm-period demand per port (weighted share)
        self.base_n = 0

    def admit_timeouts(self, fids, now, default):
        if self.inner is not None:
            return self.inner.admit_timeouts(fids, now, default)
        return np.full(len(fids), default)

    def _admit(self, fids, now):
        ok = np.ones(len(fids), bool)
        if self._inner_admit is not None:
            ok &= self._inner_admit(fids, now)
        p = self.port[fids]
        if np.isfinite(self.quota).any():
            # Rank of each new flow within its port, in arrival order.
            order = np.argsort(p, kind="stable")
            ps = p[order]
            start = np.r_[0, np.flatnonzero(np.diff(ps)) + 1]
            rank = np.arange(len(ps)) - np.repeat(start, np.diff(np.r_[start, len(ps)]))
            room = self.quota[ps] - self.used[ps]
            okq = np.empty(len(fids), bool)
            okq[order] = rank < room
            # Flows refused by the inner defense do not consume quota.
            okq |= ~ok
            self.refused[np.unique(p[~okq])] = True
            ok &= okq
        np.add.at(self.used, p[ok], 1)
        return ok

    def _scores(self, obs, idx):
        m = getattr(self.inner, "model", None)
        if (self.order != "rate" and m is not None and "X" in obs
                and getattr(self.inner, "inputs", "X") == "X"):
            X = obs["X"] if self.inner.feature_idx is None else obs["X"][:, self.inner.feature_idx]
            return m.predict_proba(X[idx])
        # No detector: evict the lowest packet rate first.
        age = np.maximum(obs["t"] - obs["install_t"][idx], 1.0)
        return -obs["pkts"][idx] / age

    def _level(self, counts, refused, cap):
        """Per-port quota array, or None if every port's demand fits."""
        d = np.where(refused, np.inf, counts)
        if self.share == "equal":
            L = water_level(d, self.q * cap)
            return np.full(len(d), max(int(np.floor(L)), 1)) if np.isfinite(L) else None
        w = np.maximum(self.base, 0.01 * self.q * cap / len(d))
        lam = weighted_level(d, w, self.q * cap)
        return np.maximum(np.floor(w * lam), 1) if np.isfinite(lam) else None

    def _update_base(self, t, obs):
        if self.share != "weighted" or t <= self.active_until or obs["count"] / obs["capacity"] >= self.rho_q:
            return
        c = np.bincount(self.port[obs["fids"]], minlength=len(self.base)).astype(float)
        self.base_n += 1
        a = max(1.0 - np.exp(-1.0 / self.tau_s), 1.0 / self.base_n)
        self.base += a * (c - self.base)

    def _inner_poll(self, t, obs):
        if self.inner is None:
            return None, None
        enforcing = t <= self.active_until
        if self.mode == "full" or not enforcing:
            return self.inner.on_poll(t, obs)
        if self.mode == "gated":
            return None, None
        # scoped: the inner defense only sees entries of ports above the fair level.
        ports = self.port[obs["fids"]]
        counts = np.bincount(ports, minlength=len(self.quota)).astype(float)
        lvl = self._level(counts, self.refused, obs["capacity"])
        if lvl is None:
            return None, None
        sel = np.flatnonzero(counts[ports] > lvl[ports])
        if len(sel) == 0:
            return None, None
        sub = dict(obs)
        for k in ("fids", "pkts", "bytes", "install_t", "X", "dms"):
            if k in obs:
                sub[k] = obs[k][sel]
        return self.inner.on_poll(t, sub)

    def on_poll(self, t, obs):
        cap, fids = obs["capacity"], obs["fids"]
        self._update_base(t, obs)
        if self.mode != "full" and obs["count"] / cap >= self.rho_q:
            self.active_until = t + self.hold_s
        dels, dems = self._inner_poll(t, obs)
        gone = np.zeros(len(fids), bool)
        for arr in (dels, dems):
            if arr is not None and len(arr):
                gone |= np.isin(fids, arr)
        keep = np.flatnonzero(~gone)
        ports = self.port[fids[keep]]
        counts = np.bincount(ports, minlength=len(self.quota)).astype(float)
        if obs["count"] / cap >= self.rho_q:
            self.active_until = t + self.hold_s
        refused, self.refused = self.refused, np.zeros_like(self.refused)
        self.used = counts.copy()
        if t > self.active_until or len(keep) == 0:
            self.quota[:] = np.inf
            return dels, dems
        lvl = self._level(counts, refused, cap)
        if lvl is None:
            self.quota[:] = np.inf
            return dels, dems
        self.quota[:] = lvl
        over = np.flatnonzero(counts > lvl)
        if len(over) == 0:
            return dels, dems
        trim = []
        for p in over:
            sel = keep[ports == p]
            s = self._scores(obs, sel)
            trim.append(fids[sel[np.argsort(-s, kind="stable")[:len(sel) - int(lvl[p])]]])
        trim = np.concatenate(trim)
        self.used[over] = lvl[over]
        dels = trim if dels is None else np.concatenate([np.asarray(dels), trim])
        return dels, dems
