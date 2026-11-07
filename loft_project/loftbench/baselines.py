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


# ------------------------------------------------------------------ FTODefender
def ftod_rule_features(X):
    """FTODefender's mitigation features: pkt, byte, AvgPI (duration / pkt) and Avgsize (byte / pkt)."""
    NP, NB, DT, _, _ = rule_raw(X)
    pk = np.maximum(NP, 1.0)
    return np.column_stack([NP, NB, DT / pk, NB / pk]).astype(np.float32)


def edr(x, y, eps):
    """Edit distance on real sequences (Chen et al. 2005): elements match when |a - b| <= eps."""
    n, m = len(x), len(y)
    D = np.zeros((n + 1, m + 1))
    D[:, 0], D[0, :] = np.arange(n + 1), np.arange(m + 1)
    for i in range(1, n + 1):
        sub = (np.abs(x[i - 1] - y) > eps).astype(float)
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j - 1] + sub[j - 1], D[i - 1, j] + 1, D[i, j - 1] + 1)
    return float(D[n, m])


class FTODDetector:
    """FTODefender's detection features per poll: SFT (EDR between the window of flow counts and
    a benign benchmark window), ESIPs (entropy of the entries' source addresses) and the variation
    of the growth of new sources (VGNS, standing in for VGFSP and VGFDP, see FTODefender)."""

    def __init__(self, benchmark, eps, window=10):
        self.benchmark, self.eps, self.window = np.asarray(benchmark, float), eps, window

    def reset(self):
        self.counts = deque(maxlen=self.window)
        self.growth = deque(maxlen=self.window)
        self.seen = set()

    def features(self, obs, src):
        s = src[obs["fids"]]
        self.counts.append(obs["count"])
        u = np.unique(s)
        new = int(len(set(u.tolist()) - self.seen))
        self.seen.update(u.tolist())
        self.growth.append(new)
        sft = edr(np.asarray(self.counts, float), self.benchmark, self.eps)
        esip = _entropy(s) if len(s) else 0.0
        g = np.asarray(self.growth, float)
        vg = float(g.std(ddof=1)) if len(g) > 1 else 0.0
        return np.array([sft, esip, vg])


def critic_weights(F):
    """CRITIC weights (Diakoulaki et al. 1995) on the normalized feature matrix, as FTODefender
    Eq. 7-11: F* = (Fmax - F) / (Fmax - Fmin), C_j = S_j sum_i (1 - r_ij), w_j = C_j / sum C."""
    fmax, fmin = F.max(0), F.min(0)
    Z = (fmax - F) / np.maximum(fmax - fmin, 1e-12)
    S = Z.std(0, ddof=1)
    r = np.nan_to_num(np.corrcoef(Z, rowvar=False))
    C = S * (1 - r).sum(0)
    return C / C.sum(), fmax, fmin


class FTODefender(_SourceBlock, Defense):
    """FTODefender: Detector (detection score DS from CRITIC-weighted, max-min normalized table
    features; an attack when DS < TH1) -> Mitigator (LightGBM-LR per-rule classifier; evict every
    rule it flags; block a source whose share of the eviction list reaches TH2).

    Paper values kept: TH1 = 0.65, TH2 = 0.5, 1 s polling, the rule features (pkt, byte, AvgPI,
    Avgsize), LightGBM-LR, CRITIC weights trained offline, permanent source block.
    Deviations: the simulator has no L4 ports, so VGFSP and VGFDP are replaced by one feature of
    the same form on new source addresses (VGNS); the EDR match tolerance (eps, 5 % of the table)
    and the benchmark window (10 polls of benign training traffic) are ours (not stated); a source
    is blocked only if the eviction list holds at least min_evict rules (ours, so one or two
    evictions cannot block a host); the models are trained on the controller's own training runs."""
    name = "ftodefender"
    needs_features = True

    def __init__(self, rule_model, detector, weights, fmax, fmin, th1=0.65, th2=0.5, min_evict=20):
        self.rule_model, self.detector = rule_model, detector
        self.w, self.fmax, self.fmin = np.asarray(weights), np.asarray(fmax), np.asarray(fmin)
        self.th1, self.th2, self.min_evict = th1, th2, min_evict
        self.admit_filter = self._admit

    def reset(self, ctx):
        self._block_reset(ctx)
        self.detector.reset()
        self.last_ds = 1.0

    def score(self, f):
        z = (self.fmax - f) / np.maximum(self.fmax - self.fmin, 1e-12)
        return float(np.dot(self.w, np.clip(z, 0.0, 1.0)))

    def on_poll(self, t, obs):
        if obs["count"] == 0:
            return None, None
        self.last_ds = self.score(self.detector.features(obs, self.src))
        if self.last_ds >= self.th1:
            return None, None
        p = _p1(self.rule_model, ftod_rule_features(obs["X"]))
        dels = obs["fids"][p >= 0.5]
        if len(dels) >= self.min_evict:
            s, c = np.unique(self.src[dels], return_counts=True)
            for a in s[c / len(dels) >= self.th2].tolist():
                if a not in self.blocked:
                    self.blocked.add(a)
                    self._blocked_arr = np.array(sorted(self.blocked), np.int64)
        return dels, None


# ------------------------------------------------------------------ rDefender
class RDefender(Defense):
    """rDefender: attacked-ports detection from abnormal table-occupancy squeezing (ATOS),
    credit evaluation, deletion-number calculation and random deletion inside ports.

    Paper values kept: threshold_h 0.3, threshold_l 1.4, credit windows 8 (high) and 30 (low),
    deletion number Da = max(Nd, 2^credit) per attacked port and Nd spread evenly over all
    ports when no port is detected, EWMA weight 0.75 on the newest value.
    Not stated: the credit scale gamma (tuned on validation seeds). Deviations: the paper
    reacts to every overflow (each Packet-In refused by a full table); here the controller
    sees the table once per 1 s poll, so attacked ports are detected once per poll and the
    overflow events of the last interval are replayed: each refused Packet-In batch of size
    Nd is one event that updates the credit windows and deletes Da rules (ceil(TABLE_FULL / Nd)
    events per poll). Nd follows Eq. 3 with the paper's measured defense time T_p = 2.5 ms
    (Nd = ceil(F_p T_p), at least 1). w_h is the per-port count change since the previous
    overflow divided by the Packet-Ins in between. events="poll" keeps the first version
    (one event per poll, Nd = one poll's arrivals)."""
    name = "rdefender"

    def __init__(self, gamma=0.05, thr_h=0.3, thr_l=1.4, size_ch=8, size_cl=30, seed=0,
                 tp=0.0025, events="replay", max_events=5000):
        self.gamma, self.thr_h, self.thr_l = gamma, thr_h, thr_l
        self.size_ch, self.size_cl, self.seed = size_ch, size_cl, seed
        self.tp, self.events, self.max_events = tp, events, max_events

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
        if self.events == "poll":
            nd, n_ev = max(int(np.ceil(self.fp)), 1), 1
        else:
            nd = max(int(np.ceil(self.fp * self.tp)), 1)
            n_ev = min(max(int(np.ceil(obs["table_full_last"] / nd)), 1), self.max_events)
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
        # Credit evaluation (Algorithm 2) and random deletion, once per overflow event.
        da = {p: 0 for p in range(self.n_ports)}
        for _ in range(n_ev):
            if not pa:
                for p in da:
                    da[p] += int(np.ceil(nd / self.n_ports))
            else:
                hist = self.ch if flag == "H" else self.cl
                for p in range(self.n_ports):
                    hist[p].append(1 if p in pa else 0)
                for p in pa:
                    da[p] += max(nd, 2 ** min(sum(hist[p]), 20))
        ports = self.port[fids]
        dels = []
        for p, k in da.items():
            own = fids[ports == p]
            if len(own) and k > 0:
                dels.append(self.rng.choice(own, min(k, len(own)), replace=False))
        return (np.concatenate(dels) if dels else None), None


class SIFT(Defense):
    """SIFT, as the comparison papers use it (FTMaster, FTODefender, FTOP, FloRa, rDefender,
    DMS-BTT): sampling-based eviction of low-rate entries. No paper we compare against states
    its parameters, so these follow the one-line description: once the table is at least
    `trigger` full, each poll samples a fraction `q` of the entries at random and deletes the
    sampled entries older than `min_age` s whose mean rate (packets / age) is below `r_low`
    packets/s. q and r_low are tuned on validation seeds (gate G1, docs/testbed_plan.md)."""
    name = "sift"

    def __init__(self, q=0.1, r_low=0.5, trigger=0.8, min_age=2.0, seed=0):
        self.q, self.r_low, self.trigger, self.min_age, self.seed = q, r_low, trigger, min_age, seed

    def reset(self, ctx):
        self.rng = np.random.default_rng(self.seed)

    def on_poll(self, t, obs):
        fids = obs["fids"]
        if obs["count"] < self.trigger * obs["capacity"] or not len(fids):
            return None, None
        pick = self.rng.random(len(fids)) < self.q
        age = np.maximum(t - obs["install_t"], 1e-3)
        low = pick & (age >= self.min_age) & (obs["pkts"] / age < self.r_low)
        return fids[low], None


class TableGuard(Defense):
    """TableGuard, as the comparison papers use it (FTODefender, FTOP, rDefender, FTShield,
    DMS-BTT): table-usage-triggered eviction of small, long-lived rules. Parameters are not
    stated in the papers we compare against: above `high` usage, entries older than `min_age`
    s with mean rate below `r_small` packets/s are deleted, oldest first, until usage is back
    to `low`. min_age and r_small are tuned on validation seeds (gate G1)."""
    name = "tableguard"

    def __init__(self, min_age=20.0, r_small=0.5, high=0.8, low=0.7):
        self.min_age, self.r_small, self.high, self.low = min_age, r_small, high, low

    def on_poll(self, t, obs):
        fids, cap = obs["fids"], obs["capacity"]
        if obs["count"] < self.high * cap or not len(fids):
            return None, None
        age = np.maximum(t - obs["install_t"], 1e-3)
        cand = np.flatnonzero((age >= self.min_age) & (obs["pkts"] / age < self.r_small))
        n = int(obs["count"] - self.low * cap)
        if n <= 0 or not len(cand):
            return None, None
        return fids[cand[np.argsort(-age[cand], kind="stable")[:n]]], None
