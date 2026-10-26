import numpy as np

from loftbench.config import DOMAINS, VARIANTS, SimConfig
from loftbench.data import collect_run
from loftbench.defenses import DualGuard, OVSEvict
from loftbench.experiment import ONLINE_SEEDS, SPLITS
from loftbench.features import FEATURE_NAMES
from loftbench.models import MLP, Standardizer, threshold_at_fpr, train_federated
from loftbench.sim import run_episode
from loftbench.traffic import Traffic, build_traffic, generate_attack


def make_traffic(pkts, n_flows, attack=None):
    """pkts: list of (t, fid). Sizes are 100 B."""
    pkts = sorted(pkts)
    t = np.array([p[0] for p in pkts], float)
    f = np.array([p[1] for p in pkts], np.int32)
    att = np.zeros(n_flows, bool) if attack is None else np.asarray(attack)
    return Traffic(t, f, np.full(len(t), 100, np.int32), att,
                   np.arange(n_flows, dtype=np.int64), np.zeros(n_flows, np.int8), [])


def test_distinct_flows_create_entries_up_to_capacity():
    cfg = SimConfig(capacity=11, infra_rules=1, duration=3.0)
    tr = make_traffic([(0.05 + 0.01 * i, i) for i in range(15)], 15)
    res = run_episode(tr, cfg)
    s = res.summary
    assert s["installs"] == 10                 # capacity minus table-miss rule
    assert s["table_full"] == 5                # five rejected admissions
    assert s["first_overflow_s"] is not None
    assert res.timeseries[0]["occupancy"] == 10 / 11


def test_idle_timeout_expires_and_refresh_keeps_entry():
    cfg = SimConfig(capacity=100, duration=30.0, idle_timeout=10.0)
    # flow 0: single packet; flow 1: refreshed every 7 s (LFTO-style)
    pk = [(0.5, 0)] + [(0.5 + 7 * k, 1) for k in range(4)]
    res = run_episode(make_traffic(pk, 2), cfg)
    occ = {round(r["t"]): r["occupancy"] * 100 for r in res.timeseries}
    assert occ[5] == 2
    assert occ[12] == 1                        # flow 0 expired after 10 s idle
    assert occ[29] == 1                        # flow 1 still resident
    assert res.summary["installs"] == 2


def test_attack_recurrence_respects_step_and_cap():
    v = VARIANTS["A2"]
    t, f, _, src, _ = generate_attack(v, 0.0, 400.0, 0, 0, np.random.default_rng(0))
    assert len(src) == v.n_attackers * v.max_flows
    # first burst of each attacker opens exactly S flows
    first_burst = f[t < 0.5 + v.step / v.burst_pps]
    assert len(np.unique(first_burst)) <= v.n_attackers * v.step


def test_labels_from_provenance_and_paired_benign_traffic():
    p = DOMAINS["D1"]
    a = build_traffic(p, 0, VARIANTS["A1"], 7, 120, 50)
    b = build_traffic(p, 0, None, 7, 120, 50)
    nb = int((~a.flow_attack).sum())
    assert nb == b.n_flows and not b.flow_attack.any()
    ben = ~a.flow_attack[a.pkt_fid]
    assert np.allclose(np.sort(a.pkt_t[ben]), np.sort(b.pkt_t))   # identical benign traffic
    assert a.pkt_t[~ben].min() >= 50                               # attack starts at onset


def test_no_defense_attack_overflows_and_benign_does_not():
    cfg = SimConfig(duration=200)
    att = run_episode(build_traffic(DOMAINS["D1"], 0, VARIANTS["A3"], 1, 200, 50), cfg).summary
    ben = run_episode(build_traffic(DOMAINS["D1"], 0, None, 1, 200, 50), cfg).summary
    assert att["overflow_seconds"] > 0 and att["benign_flows_rejected_frac"] > 0.05
    assert ben["overflow_seconds"] == 0 and ben["benign_flows_rejected_frac"] == 0


def test_feature_schema_and_state_labels():
    ds = collect_run("D2", "A2", 5, SimConfig(duration=150), frac=0.05)
    assert ds.X.shape[1] == len(FEATURE_NAMES)
    assert np.isfinite(ds.X).all()
    st = ds.state
    assert set(np.unique(st[st[:, 4] < 50, 2])) == {0}             # pre-onset is normal
    assert (st[:, 2] > 0).any()


def test_federated_weights_are_applied_and_aggregated():
    r = np.random.default_rng(0)
    X1, X2 = r.normal(size=(500, 4)), r.normal(1, 1, size=(500, 4))
    y1, y2 = (X1[:, 0] > 0).astype(int), (X2[:, 1] > 1).astype(int)
    g, comm, _ = train_federated([(X1, y1), (X2, y2)], rounds=3)
    assert comm["uplink_bytes"] == 3 * 2 * g.n_bytes()
    m = MLP(4)
    m.scaler = g.scaler
    before = m.predict_proba(X1)
    m.set_weights(g.get_weights())
    assert not np.allclose(before, m.predict_proba(X1))
    assert np.allclose(m.predict_proba(X1), g.predict_proba(X1))
    st = Standardizer.from_stats([Standardizer.stats(X1), Standardizer.stats(X2)])
    assert np.allclose(st.mean, np.vstack([X1, X2]).mean(0), atol=1e-5)


def test_threshold_budget():
    s = np.random.default_rng(1).random(10000)
    tau = threshold_at_fpr(s, 0.01)
    assert (s >= tau).mean() <= 0.01


def test_demoted_flow_reinstalled_with_short_timeout():
    class Always:
        def predict_proba(self, X):
            return np.ones(len(X))
    cfg = SimConfig(capacity=10, duration=20.0)
    pk = [(0.2 + 5 * k, 0) for k in range(4)]
    d = DualGuard(Always(), 0.5, rho=0.0, hard=False, t_short=1.0)
    res = run_episode(make_traffic(pk, 1, attack=[True]), cfg, d)
    occ = [r["occupancy"] for r in res.timeseries]
    # entry demoted at the first poll, then reinstalled for ~1 s per refresh
    assert res.summary["demotes"] >= 1
    assert sum(o > 0 for o in occ) <= 8


def test_ovs_evict_never_rejects():
    cfg = SimConfig(capacity=6, duration=5.0)
    tr = make_traffic([(0.05 + 0.2 * i, i) for i in range(20)], 20)
    s = run_episode(tr, cfg, OVSEvict()).summary
    assert s["table_full"] == 0 and s["evictions"] == 15


def test_splits_are_disjoint():
    seeds = [set(v) for v in SPLITS.values()] + [set(ONLINE_SEEDS)]
    assert sum(len(s) for s in seeds) == len(set().union(*seeds))


class _DeleteAllOnce:
    """Test defense: delete every entry at the first poll at or after t_del."""
    name = "delete-once"
    needs_features = False
    evict_on_full = None

    def __init__(self, t_del):
        self.t_del, self.done = t_del, False

    def reset(self, ctx):
        pass

    def admit_timeouts(self, fids, now, default):
        return np.full(len(fids), default)

    def on_poll(self, t, obs):
        if not self.done and t >= self.t_del:
            self.done = True
            return obs["fids"], None
        return None, None


def test_active_vs_stale_eviction_harm():
    cfg = SimConfig(capacity=100, duration=20.0, idle_timeout=10.0)
    # flow 0 sends again 3 s after the deletion (entry would still be alive): harmed.
    # flow 1 never sends again: its entry was stale, deleting it costs nothing.
    # flow 2 sends again 12 s after its last packet (entry would have expired): not harmed.
    pk = [(0.5, 0), (5.0, 0), (0.5, 1), (0.5, 2), (12.6, 2)]
    s = run_episode(make_traffic(pk, 3), cfg, _DeleteAllOnce(2.0)).summary
    assert s["benign_flows_evicted_frac"] == 1.0
    assert abs(s["benign_flows_active_evicted_frac"] - 1 / 3) < 1e-9
    assert abs(s["benign_flows_stale_evicted_frac"] - 2 / 3) < 1e-9
    assert abs(s["benign_flows_harmed_frac"] - 1 / 3) < 1e-9
    assert s["benign_evict_repackets"] == 1


def test_rejection_counts_as_harm():
    cfg = SimConfig(capacity=3, infra_rules=1, duration=2.0)
    tr = make_traffic([(0.05 + 0.01 * i, i) for i in range(4)], 4)
    s = run_episode(tr, cfg).summary
    assert s["benign_flows_harmed_frac"] == 0.5 and s["benign_flows_active_evicted_frac"] == 0


def test_cluster_bootstrap():
    import pandas as pd
    from loftbench.revision1 import cluster_boot
    df = pd.DataFrame(dict(domain=["D1"] * 4 + ["D2"] * 4, seed=[1, 1, 2, 2] * 2,
                           m=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]))
    mu, lo, hi = cluster_boot(df, "m")
    assert mu == lo == hi == 1.0
    df["m"] = [0, 0, 0, 0, 1, 1, 1, 1]          # clusters differ: CI must widen
    mu, lo, hi = cluster_boot(df, "m", n=2000)
    assert mu == 0.5 and lo < 0.5 < hi
