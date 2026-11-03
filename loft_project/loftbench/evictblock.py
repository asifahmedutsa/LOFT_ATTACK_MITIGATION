"""Detect, evict, block: the defense redesigned after the related papers (FTMaster, FTODefender:
evict the attack entries, then block the source), with a federated detector and a two-condition
block rule.

Every poll while the table is at least rho full (or a released host is on probation):
  detect  score every entry with the detector;
  evict   delete every entry scoring >= tau (no score-ordered overflow guard: when detection
          misses, as under E9P, such a guard deletes mostly benign entries; a full table is
          PortGuard's job);
  block   per host (access port, which port security ties to one MAC): over the last W s, if
          at least n_min of its entries were evicted AND at least k x as many as the median host's
          (outlier among the hosts on the switch: measured on seed 2001, attackers evict 4-40x
          the typical host under every attack, E9P included, while fixed counts overlap across
          domains), delete all its entries and refuse its new flows for
          block_s x 2^(k-1) (k-th block of that host, at most MAX_BLOCK_S); after release it
          stays on probation (scored at every poll) for 2 W.
  limit   the whole runs inside PortGuard (the frozen system's knobs, but mode "full" so that
          detection and blocking keep running while PortGuard enforces): under table pressure no
          host may hold more than its weighted fair share, the safety net when detection misses.

In the names, f is k. Round 2 (share = flagged fraction of held entries, PortGuard gated) was
stopped: gated PortGuard pauses detection while it enforces, and a held-fraction share stays
low for an attacker that keeps replacing evicted entries.
Round 1 (2026-11-03, no PortGuard, fixed 30 s blocks, share = evicted / held summed over the
window, which counts an entry once per poll) failed on development seeds: A4 refilled the table
after every release and E9P was never blocked (benign harm 37-38 %). Its episodes are kept in
select_round1_episodes.csv.

Stages (development seeds select, fresh seeds test once):
  select  detector {ens: RF 50/12 + CatBoost by model sharing, mlp: the frozen v2.1 MLP} x
          tau budget {0.2, 0.1 %} x n_min {50, 100} x k {3, 5}, first block 60 s (round 3 grid,
          from the eviction counts measured on seed 2001); D1-D3; A2, A4,
          E9P, A6, benign; validation seeds 2000-2002. Rule, per detector: settings with no
          benign host blocked in any episode and mean attack occupancy after the attack start
          <= the frozen system's + 1 point; among them the lowest mean benign harm over all
          cells (ties within 0.05: fewer evictions of benign entries).
  test    none, the frozen system (v2.1+pg), DMS-BTT with blocklist, the selected setting of each
          detector, and each selected setting without PortGuard (ablation); same cells on fresh
          seeds 26000-26004; one shot.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.evictblock {select,test} [--workers 4]

Writes results/evictblock/{select_episodes.csv, select_summary.csv, selected.json,
test_episodes.csv, test_summary.csv}.
"""
import argparse
import itertools
import json
import os
import pickle
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import flowhold as FH
from . import ml_compare as M
from .config import DOMAINS, attack_variant
from .data import DOMAIN_IDX
from . import revision5 as R5
from .defenses import Defense, PortGuard
from .e3_ens import _models as _ens_models
from .experiment import SPLITS, _dump
from .models import threshold_at_fpr
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/evictblock"
DOMS = ["D1", "D2", "D3"]
VARS = ["A2", "A4", "E9P", "A6", "benign"]
BUDGETS = (0.002, 0.001)
BLOCK_RULES = ((50, 3.0), (50, 5.0), (100, 3.0), (100, 5.0))   # (n_min, k)
BLOCK_S = (60.0,)
TEST_SEEDS = list(range(26000, 26005))
MAX_BLOCK_S = 240.0
N_BENIGN_PORTS = 4          # dedicated ports: hosts 0-3 benign, 4-5 attackers
_C = {}


class EvictBlock(Defense):
    needs_features = True

    def __init__(self, model, tau, feature_idx=None, name="evictblock", rho=0.5, h_crit=0.90,
                 target=0.80, window_s=10.0, n_min=20, f_min=0.5, block_s=30.0):
        self.model, self.tau, self.feature_idx, self.name = model, tau, feature_idx, name
        self.rho, self.h_crit, self.target = rho, h_crit, target
        self.window_s, self.n_min, self.f_min, self.block_s = window_s, n_min, f_min, block_s
        self.admit_filter = self._admit

    def reset(self, ctx):
        self.port = ctx["flow_port"]
        n_ports = int(self.port.max()) + 1
        self.blocked_until = np.full(n_ports, -np.inf)
        self.probation_until = np.full(n_ports, -np.inf)
        self.hist = []                       # (t, evicted per port, flagged fraction per port)
        self.blocks = []                     # (t, port)
        self.n_blocks = np.zeros(n_ports, int)
        self.share_max = np.zeros(n_ports)   # diagnostics: highest windowed share per host
        self.ev_max = np.zeros(n_ports)      # diagnostics: most evictions in a window per host
        self.seen = np.zeros(n_ports, bool)  # hosts that have held an entry

    def _admit(self, fids, now):
        return self.blocked_until[self.port[fids]] <= now

    def on_poll(self, t, obs):
        cap, n, fids = obs["capacity"], obs["count"], obs["fids"]
        n_ports = len(self.blocked_until)
        released = (self.blocked_until <= t) & (self.blocked_until > t - obs.get("dt", 1.0) - 1e-9)
        self.probation_until[released] = t + 2 * self.window_s
        if n == 0 or (n / cap < self.rho and not (self.probation_until > t).any()):
            self.hist.append((t, np.zeros(n_ports)))
            return None, None
        X = obs["X"] if self.feature_idx is None else obs["X"][:, self.feature_idx]
        s = self.model.predict_proba(X)
        flag = s >= self.tau
        if n / cap < self.rho:               # below pressure: act on probation hosts only
            flag &= self.probation_until[self.port[fids]] > t
        p = self.port[fids]
        ev = np.bincount(p[flag], minlength=n_ports).astype(float)
        self.seen |= np.bincount(p, minlength=n_ports) > 0
        self.hist.append((t, ev))
        self.hist = [h for h in self.hist if h[0] > t - self.window_s]
        ev_w = np.sum([h[1] for h in self.hist], axis=0)
        med = float(np.median(ev_w[self.seen])) if self.seen.any() else 0.0
        share = ev_w / max(med, 1.0)         # evictions relative to the median host
        self.share_max = np.maximum(self.share_max, np.where(ev_w >= self.n_min, share, 0.0))
        self.ev_max = np.maximum(self.ev_max, ev_w)
        new_block = (ev_w >= self.n_min) & (share >= self.f_min) & (self.blocked_until <= t)
        for q in np.flatnonzero(new_block):
            self.n_blocks[q] += 1
            self.blocked_until[q] = t + min(self.block_s * 2 ** (self.n_blocks[q] - 1), MAX_BLOCK_S)
            self.blocks.append((t, int(q)))
        gone = flag | (self.blocked_until[p] > t)
        return fids[gone], None


def _key(det, budget, rule, block_s=30.0):
    return f"eb-{det}-b{budget:g}-n{rule[0]}f{rule[1]:g}-s{block_s:g}"


def _parse(name):
    _, det, b, nf, *rest = name.split("-")
    n, f = nf[1:].split("f")
    return det, float(b[1:]), (int(n), float(f)), float(rest[0][1:]) if rest else 30.0


def _load():
    FH._load()
    _C.update(_ens_models())
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    _C["thr"] = {}
    for d in DOMS:
        v = data[("val", d)]
        dg = FH._dg(d)
        Xm = v.X if dg.feature_idx is None else v.X[:, dg.feature_idx]
        sb = {"ens": _C["ens"].predict_proba(v.X[v.y == 0]),
              "mlp": dg.model.predict_proba(Xm[v.y == 0])}
        for det, b in itertools.product(sb, BUDGETS):
            _C["thr"][(det, b, d)] = threshold_at_fpr(sb[det], b)


def _make(name, d):
    if name.endswith("-nopg"):               # ablation: the same defense without PortGuard
        return _make(name[:-5], d).inner
    if name == "none":
        return Defense()
    if name in ("v2.1+pg", "dms-blocklist"):
        return FH._make(name, d)
    det, b, (n_min, f_min), block_s = _parse(name)
    dg = FH._dg(d)
    model, fidx = (_C["ens"], None) if det == "ens" else (dg.model, dg.feature_idx)
    eb = EvictBlock(model, _C["thr"][(det, b, d)], feature_idx=fidx, name=name, rho=dg.rho,
                    h_crit=dg.h_crit, target=dg.target, n_min=n_min, f_min=f_min, block_s=block_s)
    # PortGuard's selected knobs except mode: "gated" (the frozen system's) pauses the inner
    # defense while PortGuard enforces, which stops detection and blocking exactly when the
    # table is full; "full" keeps them running.
    P = R5._CTX["P"]
    pg = PortGuard(eb, name=name, mode="full", **{x: P[x] for x in ("share", "q", "rho_q",
                                                                    "hold_s", "tau_s")})
    return pg


def _episode(args):
    stage, name, d, v, s = args
    att = None if v == "benign" else attack_variant(v)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], att, s, FH.CFG.duration,
                                    FH.CFG.attack_start), "dedicated")
    df = _make(name, d)
    r = run_episode(tr, FH.CFG, df, record_ts=False).summary
    blocks = getattr(getattr(df, "inner", None), "blocks", None) or getattr(df, "blocks", [])
    return dict(stage=stage, defense=name, domain=d, variant=v, seed=s,
                benign_hosts_blocked=len({q for _, q in blocks if q < N_BENIGN_PORTS}),
                attack_hosts_blocked=len({q for _, q in blocks if q >= N_BENIGN_PORTS}),
                first_attack_block_s=min([t for t, q in blocks if q >= N_BENIGN_PORTS],
                                         default=np.nan) - FH.CFG.attack_start, **r)


def _run(tasks, workers):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=1)):
            rows.append(row)
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def _summary(df):
    g = df.groupby(["defense", "variant"])
    tab = pd.DataFrame({
        "harm_pct": 100 * g.benign_flows_harmed_frac.mean(),
        "attack_occ_pct": 100 * g.avg_attack_occ_post.mean(),
        "benign_hosts_blocked": g.benign_hosts_blocked.mean(),
        "attack_hosts_blocked": g.attack_hosts_blocked.mean(),
        "first_block_s": g.first_attack_block_s.mean(),
        "benign_deletes": g.benign_deletes.mean()}).round(3)
    return tab


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    names = [_key(det, b, r, bs) for det in ("ens", "mlp") for b in BUDGETS for r in BLOCK_RULES
             for bs in BLOCK_S]
    if not os.path.exists(path):
        _load()
        cells = [(d, v, s) for d in DOMS for v in VARS for s in SPLITS["val"]]
        tasks = [("select", n, *c) for n in ["v2.1+pg"] + names for c in cells]
        _run(tasks, workers).to_csv(path, index=False)
    df = pd.read_csv(path)
    att = df[df.variant != "benign"]
    ref_occ = 100 * att[att.defense == "v2.1+pg"].avg_attack_occ_post.mean()
    rows = []
    for n in names:
        a, all_ = att[att.defense == n], df[df.defense == n]
        rows.append(dict(defense=n, harm_pct=100 * all_.benign_flows_harmed_frac.mean(),
                         attack_occ_pct=100 * a.avg_attack_occ_post.mean(),
                         benign_host_blocks=int(all_.benign_hosts_blocked.sum()),
                         benign_deletes=all_.benign_deletes.mean(),
                         eligible=bool(all_.benign_hosts_blocked.sum() == 0
                                       and 100 * a.avg_attack_occ_post.mean() <= ref_occ + 1)))
    s = pd.DataFrame(rows).round(3)
    s.to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    sel = {}
    for det in ("ens", "mlp"):
        ok = s[s.eligible & s.defense.str.startswith(f"eb-{det}-")]
        if ok.empty:
            sel[det] = None
            continue
        best = ok.harm_pct.min()
        near = ok[ok.harm_pct <= best + 0.05]
        sel[det] = near.sort_values("benign_deletes").defense.iloc[0]
    ref = df[df.defense == "v2.1+pg"]
    _dump(OUT, "selected.json", dict(selected=sel, frozen_attack_occ_pct=round(ref_occ, 3),
                                     frozen_harm_pct=round(100 * ref.benign_flows_harmed_frac.mean(), 3)))
    pd.set_option("display.width", 200)
    print(s.to_string(index=False))
    print(_summary(df[df.defense.isin(["v2.1+pg", *[x for x in sel.values() if x]])]).to_string())
    print(json.dumps(sel))


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    _load()
    defs = ["none", "v2.1+pg", "dms-blocklist"] + [x for x in sel.values() if x] + \
        [x + "-nopg" for x in sel.values() if x]
    if sel.get("ens") and not sel.get("mlp"):
        # Ablation: the selected setting with the frozen MLP as detector (no MLP setting passed
        # selection: it blocked benign hosts).
        defs.append(sel["ens"].replace("eb-ens-", "eb-mlp-"))
    tasks = [("test", n, d, v, s) for n in defs for d in DOMS for v in VARS for s in TEST_SEEDS]
    df = _run(tasks, workers)
    df.to_csv(path, index=False)
    tab = _summary(df)
    tab.to_csv(os.path.join(OUT, "test_summary.csv"))
    pd.set_option("display.width", 200)
    print(tab.to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["select", "test"])
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    {"select": stage_select, "test": stage_test}[a.stage](a.workers)


if __name__ == "__main__":
    main()
