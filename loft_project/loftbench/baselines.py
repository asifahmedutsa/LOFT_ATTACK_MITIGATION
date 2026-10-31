"""Reimplementations of four published LFTO defenses for same-simulator comparison (E2).

Each class follows its paper's algorithm and stated parameters; every place where our
simulator forces a change is listed in the class docstring. All run at the controller's
1 s stats poll, like DMS-BTT and DualGuard, and see the same observation (installed entries
with packet and byte counters, install time, our per-rule features, source address and
ingress port).

  FTMaster   Tang et al., IEEE TNSM 2023
  FTOP       Tang et al., IEEE TNSE 2024 (online July 2023)
  FloRa      Mudgal et al., IEEE TNSM 2024
  rDefender  Kong et al., IEEE TIFS 2024
"""
from collections import deque

import numpy as np

from .sim import Defense


# ------------------------------------------------------------------ shared helpers
def rule_raw(X):
    """Raw per-rule counters recovered from our feature matrix (features.FeatureTracker)."""
    NP = np.expm1(X[:, 0].astype(float))
    NB = np.expm1(X[:, 1].astype(float))
    DT = np.maximum(np.expm1(X[:, 2].astype(float)), 1e-3)
    MPS = X[:, 3].astype(float) * 1500.0
    MPIT = np.expm1(X[:, 5].astype(float))
    return NP, NB, DT, MPS, MPIT


def ftmaster_rule_features(X):
    """FTMaster's six rule features: DT, NP, NB, MPS, MPIT, MTS."""
    NP, NB, DT, MPS, MPIT = rule_raw(X)
    return np.column_stack([DT, NP, NB, MPS, MPIT, NB / DT]).astype(np.float32)


def ftop_rule_features(X):
    """FTOP's mitigation features without IPs and ports: pkt, byte, APAI (pkt / duration),
    APS (mean packet size)."""
    NP, NB, DT, MPS, _ = rule_raw(X)
    return np.column_stack([NP, NB, NP / DT, MPS]).astype(np.float32)


def flora_rule_features(X):
    """FloRa's flow features available in simulation: duration, packets, bytes, mean size,
    packet arrival frequency (PAF) as rate and mean gap, and the gap coefficient of variation."""
    NP, NB, DT, MPS, MPIT = rule_raw(X)
    return np.column_stack([DT, NP, NB, MPS, NP / DT, MPIT, X[:, 9], X[:, 10]]).astype(np.float32)


def _cv(x):
    m = x.mean()
    return float(x.std() / m) if m > 0 else 0.0


def _entropy(v):
    _, c = np.unique(v, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def ftmaster_table_features(t, obs, src):
    """MT, MB, MP, CVT, CVB, CVP, DDoIP (entropy of source IPs) and occupancy."""
    if obs["count"] == 0:
        return np.zeros(8, np.float32)
    dur = np.maximum(t - obs["install_t"], 0.0)
    b, p = obs["bytes"].astype(float), obs["pkts"].astype(float)
    return np.array([dur.mean(), b.mean(), p.mean(), _cv(dur), _cv(b), _cv(p),
                     _entropy(src[obs["fids"]]), obs["count"] / obs["capacity"]], np.float32)


def ftop_table_features(obs):
    """pkt, byte, numrules, avgpkt (Eq. 7)."""
    n = obs["count"]
    pk = float(obs["pkts"].sum())
    return np.array([pk, float(obs["bytes"].sum()), n, pk / max(n, 1)], np.float32)


def _p1(model, Z):
    p = model.predict_proba(Z)
    return p[:, 1] if np.ndim(p) == 2 else p


class _SourceBlock:
    """Controller drop rules on source addresses (FTMaster, FloRa)."""

    def _block_reset(self, ctx):
        self.src = ctx["flow_src"]
        self.del_count = {}
        self.blocked = set()
        self._blocked_arr = np.zeros(0, np.int64)

    def _count_and_block(self, del_fids, limit):
        if len(del_fids) == 0:
            return
        s, c = np.unique(self.src[del_fids], return_counts=True)
        for a, k in zip(s.tolist(), c.tolist()):
            n = self.del_count.get(a, 0) + k
            self.del_count[a] = n
            if n > limit and a not in self.blocked:
                self.blocked.add(a)
                self._blocked_arr = np.array(sorted(self.blocked), np.int64)

    def _admit(self, fids, now):
        if len(self._blocked_arr) == 0:
            return np.ones(len(fids), bool)
        return ~np.isin(self.src[fids], self._blocked_arr)


# ------------------------------------------------------------------ FTMaster
class FTMaster(_SourceBlock, Defense):
    """FTMaster: monitor -> XGBoost table-state detector -> XGBoost per-rule classifier ->
    evict attack rules (elephants protected) -> block a source once its deleted-rule count
    exceeds 50 % of the table size.

    Paper values kept: detection threshold 70 % of the table (on the mean of the latest
    polls), elephant filter (NB and MPS above the 90th percentile), block limit 0.5 x table.
    Deviations: table features omit DDoP and CDD (the simulator has no L4 ports); the classifiers
    are trained per controller on its own training runs, like DMS-BTT."""
    name = "ftmaster"
    needs_features = True

    def __init__(self, state_model, rule_model, monitor=0.70, window=3, block_frac=0.5):
        self.state_model, self.rule_model = state_model, rule_model
        self.monitor, self.window, self.block_frac = monitor, window, block_frac
        self.admit_filter = self._admit

    def reset(self, ctx):
        self._block_reset(ctx)
        self.hist = deque(maxlen=self.window)

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        self.hist.append(n)
        if n == 0 or np.mean(self.hist) < self.monitor * cap:
            return None, None
        f = ftmaster_table_features(t, obs, self.src)[None, :]
        if int(np.ravel(self.state_model.predict(f))[0]) == 0:
            return None, None
        p = _p1(self.rule_model, ftmaster_rule_features(obs["X"]))
        nb, mps = obs["bytes"].astype(float), obs["bytes"] / np.maximum(obs["pkts"], 1)
        eleph = (nb > np.percentile(nb, 90)) & (mps > np.percentile(mps, 90))
        dels = obs["fids"][(p >= 0.5) & ~eleph]
        self._count_and_block(dels, self.block_frac * cap)
        return dels, None


# ------------------------------------------------------------------ FTOP
class _Kalman1D:
    """Constant-velocity Kalman filter on the flow count (FTOP's Predictor, dt = 1 poll)."""

    def __init__(self, q=4.0, r=100.0):
        self.x = None
        self.P = np.eye(2) * 1e4
        self.F = np.array([[1.0, 1.0], [0.0, 1.0]])
        self.Q = np.eye(2) * q
        self.R = r

    def step(self, z):
        if self.x is None:
            self.x = np.array([z, 0.0])
        x = self.F @ self.x
        P = self.F @ self.P @ self.F.T + self.Q
        k = P[:, 0] / (P[0, 0] + self.R)
        self.x = x + k * (z - x[0])
        self.P = P - np.outer(k, P[0])
        return float((self.F @ self.x)[0])          # estimate for the next poll


class FTOP(Defense):
    """FTOP: Kalman predictor -> RF table detector -> RF per-rule mitigator, and a Preventer
    that evicts the lowest significance-score rules until the count is below TH.

    Paper values kept: TH0 = 80 % of the table, TH = alpha x TH0 with alpha = 0.7 after two
    consecutive detections, detector features (pkt, byte, numrules, avgpkt), significance
    score with CV-derived weights (Eq. 9, the alpha in its first denominator read as theta).
    Deviations: mitigation features omit IPs and ports (meaningless across simulated
    domains); Kalman noise is ours (the paper uses pykalman defaults); RFs are trained per
    controller."""
    name = "ftop"
    needs_features = True

    def __init__(self, state_model, rule_model, th0=0.80, alpha=0.70):
        self.state_model, self.rule_model = state_model, rule_model
        self.th0, self.alpha = th0, alpha

    def reset(self, ctx):
        self.kf = _Kalman1D()
        self.counter = 0

    @staticmethod
    def _ss(obs):
        x, y = obs["pkts"].astype(float), obs["bytes"].astype(float)
        th, be = _cv(x), _cv(y)
        w = th + be if th + be > 0 else 1.0
        return th / w * x / max(x.sum(), 1.0) + be / w * y / max(y.sum(), 1.0)

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        est = self.kf.step(n)
        th = (self.alpha if self.counter >= 2 else 1.0) * self.th0 * cap
        if n == 0 or est <= th:
            return None, None
        attack = int(np.ravel(self.state_model.predict(ftop_table_features(obs)[None, :]))[0]) == 1
        gone = np.zeros(n, bool)
        if attack:
            self.counter += 1
            gone |= _p1(self.rule_model, ftop_rule_features(obs["X"])) >= 0.5
        else:
            self.counter = 0
        # Preventer: after mitigation (or when no attack is detected), evict the
        # least significant rules until the count is below TH.
        k = int(n - gone.sum() - th) + 1
        if k > 0:
            rest = np.flatnonzero(~gone)
            ss = self._ss(obs)[rest]
            gone[rest[np.argsort(ss, kind="stable")[:k]]] = True
        return obs["fids"][gone], None


# ------------------------------------------------------------------ FloRa
class FloRa(_SourceBlock, Defense):
    """FloRa: flow analyzer (count above a threshold, rules older than 100 s are suspicious),
    anomaly predictor (possible spoofed IP via BCP38), CatBoost classifier, mitigation
    (delete and blacklist flagged rules, protect elephants, block sources whose flagged count
    exceeds a limit).

    Paper values kept: 100 s duration threshold, CatBoost, elephant protection.
    Not stated in the paper, so tuned on validation seeds like every other knob: the
    occupancy trigger and the per-source block limit. Deviations: CRS (payload entropy)
    cannot be computed without payloads and is dropped; BCP38 is read as "source outside
    the internal 10.0.0.0/8 network"; the classifier is trained per controller."""
    name = "flora"
    needs_features = True

    def __init__(self, rule_model, trigger=0.70, dur_s=100.0, block_after=50):
        self.rule_model = rule_model
        self.trigger, self.dur_s, self.block_after = trigger, dur_s, block_after
        self.admit_filter = self._admit

    def reset(self, ctx):
        self._block_reset(ctx)

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        if n == 0 or n < self.trigger * cap:
            return None, None
        src = self.src[obs["fids"]]
        psi = (src >> 24) != 10
        cand = np.flatnonzero(((t - obs["install_t"]) > self.dur_s) | psi)
        if len(cand) == 0:
            return None, None
        p = _p1(self.rule_model, flora_rule_features(obs["X"][cand]))
        byts = obs["bytes"].astype(float)
        eleph = byts[cand] >= np.percentile(byts, 90)
        dels = obs["fids"][cand[(p >= 0.5) & ~eleph]]
        self._count_and_block(dels, self.block_after)
        return dels, None


# ------------------------------------------------------------------ rDefender
class RDefender(Defense):
    """rDefender: attacked-ports detection from abnormal table-occupancy squeezing (ATOS),
    credit evaluation, deletion-number calculation and random deletion inside ports.

    Paper values kept: threshold_h 0.3, threshold_l 1.4, credit windows 8 (high) and 30 (low),
    deletion number Da = max(Nd, 2^credit) per attacked port and Nd spread evenly over all
    ports when no port is detected, EWMA weight 0.75 on the newest value.
    Not stated: the credit scale gamma (tuned on validation seeds). Deviations: detection
    runs at the 1 s poll when the table was full since the last poll (the paper reacts to
    each Packet-In); Nd is the Packet-In arrivals expected in one poll interval (the defense
    delay T_p of Eq. 3 is the poll interval here); w_h is the per-port count change since
    the previous overflow divided by the Packet-Ins in between."""
    name = "rdefender"

    def __init__(self, gamma=0.05, thr_h=0.3, thr_l=1.4, size_ch=8, size_cl=30, seed=0):
        self.gamma, self.thr_h, self.thr_l = gamma, thr_h, thr_l
        self.size_ch, self.size_cl, self.seed = size_ch, size_cl, seed

    def reset(self, ctx):
        self.port = ctx["flow_port"]
        if self.port is None:
            raise ValueError("rDefender needs traffic.flow_port (see ports.assign_ports)")
        self.n_ports = int(self.port.max()) + 1
        self.ch = [deque(maxlen=self.size_ch) for _ in range(self.n_ports)]
        self.cl = [deque(maxlen=self.size_cl) for _ in range(self.n_ports)]
        self.rng = np.random.default_rng(self.seed)
        self.fp = 0.0                  # EWMA Packet-In arrivals per poll
        self.base = None               # per-port counts at the previous overflow
        self.pi_since = 0.0            # Packet-Ins since the previous overflow
        self.last_t = 0.0

    def _counts(self, fids):
        return np.bincount(self.port[fids], minlength=self.n_ports).astype(float)

    def on_poll(self, t, obs):
        cap, fids = obs["capacity"], obs["fids"]
        new = int((obs["install_t"] > self.last_t).sum()) + int(obs["table_full_last"])
        self.last_t = t
        self.fp = 0.25 * self.fp + 0.75 * new
        self.pi_since += new
        counts = self._counts(fids)
        if self.base is None:
            self.base = counts.copy()
        if obs["count"] < cap - 1 and obs["table_full_last"] == 0:
            return None, None
        nd = max(int(np.ceil(self.fp)), 1)
        # Attacked-ports detection (Algorithm 1): high rate first, then low rate.
        flag, pa = None, []
        score_h = (counts - self.base) / max(self.pi_since, 1.0)
        for p in range(self.n_ports):
            if score_h[p] + self.gamma * sum(self.ch[p]) >= self.thr_h:
                pa.append(p)
                flag = "H"
        if not pa:
            dev = counts.std()
            z = (counts - counts.mean()) / dev if dev > 0 else np.zeros_like(counts)
            for p in range(self.n_ports):
                if z[p] + self.gamma * sum(self.cl[p]) >= self.thr_l:
                    pa.append(p)
                    flag = "L"
        self.base, self.pi_since = counts.copy(), 0.0
        # Credit evaluation (Algorithm 2).
        da = {}
        if not pa:
            per = int(np.ceil(nd / self.n_ports))
            da = {p: per for p in range(self.n_ports)}
        else:
            hist = self.ch if flag == "H" else self.cl
            for p in range(self.n_ports):
                hist[p].append(1 if p in pa else 0)
            for p in pa:
                da[p] = max(nd, 2 ** min(sum(hist[p]), 20))
        # Random deletion inside each port.
        ports = self.port[fids]
        dels = []
        for p, k in da.items():
            own = fids[ports == p]
            if len(own):
                dels.append(self.rng.choice(own, min(k, len(own)), replace=False))
        return (np.concatenate(dels) if dels else None), None
