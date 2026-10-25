"""Labeled dataset collection from simulated runs.

Entry labels come from traffic provenance (attack driver vs benign generator).
DMS-BTT state labels come from attack timing and *observed* table-full events:
0 = no attack active, 1 = attack active before overflow, 2 = attack active
after overflow. Each row records its run_id so splits never share runs.
"""
from dataclasses import dataclass

import numpy as np

from .config import DOMAINS, VARIANTS, SimConfig
from .sim import run_episode
from .traffic import build_traffic

DOMAIN_IDX = {d: i for i, d in enumerate(DOMAINS)}


@dataclass
class Dataset:
    X: np.ndarray        # our feature schema
    dms: np.ndarray      # Numb, PIT, Sizep
    y: np.ndarray        # entry label (1 = attack)
    run: np.ndarray      # run id per row
    t: np.ndarray        # poll time per row
    state: np.ndarray    # rows: FN, APIT, state_label, run, t
    runs: list           # run descriptors

    @staticmethod
    def concat(parts):
        parts = [p for p in parts if p is not None]
        return Dataset(*(np.concatenate([getattr(p, f) for p in parts])
                         for f in ("X", "dms", "y", "run", "t", "state")),
                       sum((p.runs for p in parts), []))

    def subset(self, mask):
        keep_runs = set(np.unique(self.run[mask]).tolist())
        smask = np.isin(self.state[:, 3], list(keep_runs))
        return Dataset(self.X[mask], self.dms[mask], self.y[mask], self.run[mask],
                       self.t[mask], self.state[smask],
                       [r for r in self.runs if r["run_id"] in keep_runs])


def run_id_of(domain, variant, seed):
    return DOMAIN_IDX[domain] * 10_000_000 + (0 if variant is None else int(variant[1:])) * 100_000 + seed


def collect_run(domain, variant, seed, cfg: SimConfig, frac=0.03):
    tr = build_traffic(DOMAINS[domain], DOMAIN_IDX[domain],
                       VARIANTS[variant] if variant else None, seed, cfg.duration,
                       cfg.attack_start)
    rid = run_id_of(domain, variant, seed)
    rng = np.random.default_rng(rid)
    rows_X, rows_d, rows_y, rows_t, states = [], [], [], [], []
    cap = cfg.capacity - cfg.infra_rules
    overflowed = [False]

    def active(t):
        return any(a <= t <= b + 1e-9 for a, b in tr.attack_active)

    def collect(t, fids, obs, lab):
        on = variant is not None and active(t)
        if not on:
            overflowed[0] = False
        elif obs["table_full_last"] > 0 or obs["count"] >= cap:
            overflowed[0] = True
        st = 0 if not on else (2 if overflowed[0] else 1)
        states.append((obs["state"]["FN"], obs["state"]["APIT"], st, rid, t))
        if len(fids):
            m = rng.random(len(fids)) < frac
            rows_X.append(obs["X"][m])
            rows_d.append(obs["dms"][m])
            rows_y.append(lab[m])
            rows_t.append(np.full(m.sum(), t))

    res = run_episode(tr, cfg, collect=collect, record_ts=False)
    n = sum(len(y) for y in rows_y)
    return Dataset(np.concatenate(rows_X), np.concatenate(rows_d),
                   np.concatenate(rows_y).astype(np.int8), np.full(n, rid),
                   np.concatenate(rows_t), np.array(states, dtype=np.float64),
                   [dict(run_id=rid, domain=domain, variant=variant, seed=seed,
                         first_overflow_s=res.summary["first_overflow_s"])])


def collect_domain(domain, variants, seeds, cfg, benign_runs=True, frac=0.03):
    parts = []
    for s in seeds:
        for v in variants:
            parts.append(collect_run(domain, v, s, cfg, frac))
        if benign_runs:
            parts.append(collect_run(domain, None, s, cfg, frac))
    return Dataset.concat(parts)
