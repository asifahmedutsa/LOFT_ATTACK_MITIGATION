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
