"""Do our rDefender and FloRa reimplementations reproduce their own papers?

E2 ran every defense under DMS-BTT's setting (3,500 entries, idle timeout 10 s, LFTO
attacks A1-A7), where rDefender and FloRa did not halve the attacker's table share. Here
each runs under its own paper's setting and is checked against the direction its paper
reports. FL-DualGuard v2.1 runs alongside, transferred unchanged (model and thresholds
from the main setting).

rDefender setting (TIFS 2024): idle timeout 30 s, attacker on its own port, attacks
  LA  low-rate flood: 300 new one-packet flows per second (64 B), never refreshed
  HA  high-rate flood: 2,000 new one-packet flows per second
  plus our LFTO A2 and the mimicry A4 (close to rDefender's ALA trace replay).
  Paper direction: malicious rules on the attacked switch stay low (below 10 under HA),
  lower than FIFO and LRU, with no Packet-In loss.
FloRa setting (TNSM 2024): idle timeout 20 s, FIFO replacement in the switch, 1,000 s
  runs with the attack from 300 s, 3 attackers, attack sets (period, packets) F1 (4-8 s,
  20), F2 (8-12 s, 40), F3 (12-16 s, 60), F4 (16-19 s, 80). FloRa's CatBoost is retrained
  on runs collected in this setting (seeds 1000-1001; offline accuracy on seed 1002).
  Paper direction: attack rules stay below 35 % of the table and fall to about 0 once
  sources are blocked; far fewer overflows than without a defense.

Deviation in both: our benign traffic alone overflows a 2,000-entry table at these idle
timeouts, so the table is sized for the same benign share as in the main setting:
5,000 entries for rDefender's 30 s timeout, 4,000 (inside FloRa's tested range) for 20 s.
Seeds 13000-13004 (unused).

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e2_repro [--workers 4]
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import pickle
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import e2_baselines as E2
from . import v21
from .baselines import FloRa, RDefender, flora_rule_features
from .config import DOMAINS, VARIANTS, AttackVariant, SimConfig
from .data import DOMAIN_IDX
from .defenses import OVSEvict
from .ports import assign_ports
from .sim import Defense, run_episode
from .traffic import build_traffic

OUT = "results/e2_baselines/repro"
SEEDS = list(range(13000, 13005))
RD_CFG = SimConfig(capacity=5000, idle_timeout=30.0, duration=300.0)
FL_CFG = SimConfig(capacity=4000, idle_timeout=20.0, duration=1000.0, attack_start=300.0)
ATTACKS = {
    "LA": AttackVariant("LA-flood300", 300, (1.0, 1.0), max_flows=10**9, src_mode="pool",
                        burst_pps=300.0, n_attackers=1, refresh=False),
    "HA": AttackVariant("HA-flood2000", 2000, (1.0, 1.0), max_flows=10**9, src_mode="pool",
                        burst_pps=2000.0, n_attackers=1, refresh=False),
    "A2": VARIANTS["A2"], "A4": VARIANTS["A4"],
    "F1": AttackVariant("F1", 20, (4.0, 8.0), src_mode="host", n_attackers=3),
    "F2": AttackVariant("F2", 40, (8.0, 12.0), src_mode="host", n_attackers=3),
    "F3": AttackVariant("F3", 60, (12.0, 16.0), src_mode="host", n_attackers=3),
    "F4": AttackVariant("F4", 80, (16.0, 19.0), src_mode="host", n_attackers=3),
}
SETTINGS = {"rdefender": dict(cfg=RD_CFG, attacks=["LA", "HA", "A2", "A4"],
                              defenses=["none", "lru", "rdefender", "rdefender-poll", "v2.1"]),
            "flora": dict(cfg=FL_CFG, attacks=["F1", "F2", "F3", "F4"],
                          defenses=["fifo", "flora+fifo", "v2.1+fifo"])}
_M = {}


def _fifo(n_needed, cand, last_seen, idle_to, now, install_t):
    k = min(n_needed, len(cand))
    return cand[np.argpartition(install_t[cand], k - 1)[:k]] if k > 0 else cand[:0]


def _with_fifo(d):
    d.evict_on_full = _fifo
    d.evict_needs_install = True
    return d


def _make(name, d):
    if name == "none":
        return Defense()
    if name == "lru":
        return OVSEvict()
    if name == "fifo":
        return _with_fifo(Defense())
    if name == "rdefender":
        return RDefender(**{**_M["knobs"]["rdefender"], "events": "replay"})
    if name == "rdefender-poll":
        return RDefender(**{**_M["knobs"]["rdefender"], "events": "poll"})
    if name == "flora+fifo":
        return _with_fifo(FloRa(_M["flora"][d], **_M["knobs"]["flora"]))
    if name == "v2.1":
        return v21._make("v2.1", d, None)
    if name == "v2.1+fifo":
        return _with_fifo(v21._make("v2.1", d, None))
    raise ValueError(name)


def _traffic(d, a, s, cfg):
    return assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], ATTACKS[a] if a else None, s,
                                      cfg.duration, cfg.attack_start), "dedicated")


# ------------------------------------------------------------------ FloRa retraining
def _collect(args):
    d, a, s = args
    tr = _traffic(d, a, s, FL_CFG)
    rng = np.random.default_rng(s * 31 + hash(a or "b") % 1000)
    X, y = [], []

    def hook(t, fids, obs, lab):
        if len(fids):
            m = rng.random(len(fids)) < 0.03
            X.append(obs["X"][m])
            y.append(lab[m])

    run_episode(tr, FL_CFG, _with_fifo(Defense()), collect=hook, record_ts=False)
    return d, s, np.concatenate(X), np.concatenate(y).astype(int)


def train_flora(workers):
    from catboost import CatBoostClassifier
    tasks = [(d, a, s) for d in DOMAINS for a in SETTINGS["flora"]["attacks"] + [None]
             for s in (1000, 1001, 1002)]
    with get_context("fork").Pool(workers) as p:
        parts = p.map(_collect, tasks)
    models, acc = {}, {}
    for d in DOMAINS:
        trX = np.concatenate([x for dd, s, x, _ in parts if dd == d and s != 1002])
        trY = np.concatenate([y for dd, s, _, y in parts if dd == d and s != 1002])
        teX = np.concatenate([x for dd, s, x, _ in parts if dd == d and s == 1002])
        teY = np.concatenate([y for dd, s, _, y in parts if dd == d and s == 1002])
        m = CatBoostClassifier(iterations=300, random_seed=0, verbose=False, thread_count=4)
        m.fit(flora_rule_features(trX), trY)
        pr = m.predict(flora_rule_features(teX)).astype(int).ravel()
        acc[d] = dict(train_rows=int(len(trY)), test_rows=int(len(teY)),
                      accuracy=float((pr == teY).mean()),
                      fpr=float(((pr == 1) & (teY == 0)).sum() / max((teY == 0).sum(), 1)),
                      fnr=float(((pr == 0) & (teY == 1)).sum() / max((teY == 1).sum(), 1)))
        models[d] = E2._OneThread(m)
    return models, acc


# ------------------------------------------------------------------ episodes
def _episode(args):
    setting, name, d, a, s = args
    cfg = SETTINGS[setting]["cfg"]
    tr = _traffic(d, a, s, cfg)
    r = run_episode(tr, cfg, _make(name, d), record_ts=True)
    ts = pd.DataFrame(r.timeseries)
    post = ts[ts.t > cfg.attack_start]
    last = ts[ts.t > cfg.duration - 60]
    S = r.summary
    return dict(setting=setting, defense=name, domain=d, attack=a, seed=s,
                harmed=100 * S["benign_flows_harmed_frac"],
                attack_share_avg=100 * S["avg_attack_occ_post"], attack_share_max=100 * S["max_attack_occ"],
                attack_rules_avg=float((post.attack_occ * cfg.capacity).mean()),
                attack_rules_last60=float((last.attack_occ * cfg.capacity).mean()),
                table_usage=100 * float(post.occupancy.mean()),
                overflow_s=S["overflow_seconds_post_attack"],
                overflow_runs=int(S["first_overflow_s"] is not None and not pd.isna(S["first_overflow_s"])),
                benign_pi_lost=100 * S["benign_rejected_pkts"] / max(S["benign_pkts"], 1),
                table_full=S["table_full"], attack_deletes=S["attack_deletes"],
                benign_deletes=S["benign_deletes"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    E2._load()
    _M["knobs"] = json.load(open(os.path.join(E2.OUT, "selected.json")))["selected"]
    _M["flora"], acc = train_flora(a.workers)
    json.dump(acc, open(os.path.join(OUT, "flora_offline.json"), "w"), indent=1)
    print("[flora retrained]", json.dumps(acc), f"{time.time() - t0:.0f} s", flush=True)
    tasks = [(st, n, d, at, s) for st, c in SETTINGS.items() for n in c["defenses"]
             for d in DOMAINS for at in c["attacks"] for s in SEEDS]
    with get_context("fork").Pool(a.workers) as p:
        rows = p.map(_episode, tasks, chunksize=2)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "episodes.csv"), index=False)
    cols = ["harmed", "attack_share_avg", "attack_share_max", "attack_rules_avg",
            "attack_rules_last60", "table_usage", "overflow_s", "overflow_runs",
            "benign_pi_lost", "table_full"]
    summ = df.groupby(["setting", "attack", "defense"])[cols].mean().round(2)
    summ.to_csv(os.path.join(OUT, "summary.csv"))
    pd.set_option("display.width", 250)
    print(summ.to_string())
    print(f"done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
