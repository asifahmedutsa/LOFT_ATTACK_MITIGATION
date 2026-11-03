"""Detect, evict, block: the defense redesigned after the related papers (FTMaster, FTODefender:
evict the attack entries, then block the source), with a federated detector and a two-condition
block rule.

Every poll while the table is at least rho full (or a released host is on probation):
  detect  score every entry with the detector;
  evict   delete every entry scoring >= tau; if the table is still >= h_crit full, delete the
          lowest-scoring non-elephant entries down to target (DualGuard's overflow guard);
  block   per host (access port, which port security ties to one MAC): over the last W s, if
          at least n_min of its entries were evicted AND they are at least f_min of the entries
          it held, delete all its entries and refuse its new flows for block_s; after release
          it stays on probation (scored at every poll) for 2 W.

Stages (development seeds select, fresh seeds test once):
  select  detector {ens: RF 50/12 + CatBoost by model sharing, mlp: the frozen v2.1 MLP} x
          tau budget {0.5, 0.2, 0.1 %} x (n_min, f_min) {(20, 0.5), (50, 0.8)}; D1-D3; A2, A4,
          E9P, A6, benign; validation seeds 2000-2002. Rule, per detector: settings with no
          benign host blocked in any episode and mean attack occupancy after the attack start
          <= the frozen system's + 1 point; among them the lowest mean benign harm over all
          cells (ties within 0.05: fewer evictions of benign entries).
  test    none, the frozen system (v2.1+pg), DMS-BTT with blocklist, and the selected setting of
          each detector; same cells on fresh seeds 26000-26004; one shot.

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
from .defenses import Defense, _elephants
from .e3_ens import _models as _ens_models
from .experiment import SPLITS, _dump
from .models import threshold_at_fpr
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/evictblock"
DOMS = ["D1", "D2", "D3"]
VARS = ["A2", "A4", "E9P", "A6", "benign"]
BUDGETS = (0.005, 0.002, 0.001)
BLOCK_RULES = ((20, 0.5), (50, 0.8))
TEST_SEEDS = list(range(26000, 26005))
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
        self.hist = []                       # (t, evicted per port, held per port)
        self.blocks = []                     # (t, port)

    def _admit(self, fids, now):
        return self.blocked_until[self.port[fids]] <= now

    def on_poll(self, t, obs):
        cap, n, fids = obs["capacity"], obs["count"], obs["fids"]
        n_ports = len(self.blocked_until)
        released = (self.blocked_until <= t) & (self.blocked_until > t - obs.get("dt", 1.0) - 1e-9)
        self.probation_until[released] = t + 2 * self.window_s
        if n == 0 or (n / cap < self.rho and not (self.probation_until > t).any()):
            self.hist.append((t, np.zeros(n_ports), np.zeros(n_ports)))
            return None, None
        X = obs["X"] if self.feature_idx is None else obs["X"][:, self.feature_idx]
        s = self.model.predict_proba(X)
        flag = s >= self.tau
        if n / cap < self.rho:               # below pressure: act on probation hosts only
            flag &= self.probation_until[self.port[fids]] > t
        p = self.port[fids]
        ev = np.bincount(p[flag], minlength=n_ports).astype(float)
        held = np.bincount(p, minlength=n_ports).astype(float)
        self.hist.append((t, ev, held))
        self.hist = [h for h in self.hist if h[0] > t - self.window_s]
        ev_w = np.sum([h[1] for h in self.hist], axis=0)
        held_w = np.sum([h[2] for h in self.hist], axis=0)
        share = ev_w / np.maximum(held_w, 1)
        new_block = (ev_w >= self.n_min) & (share >= self.f_min) & (self.blocked_until <= t)
        for q in np.flatnonzero(new_block):
            self.blocked_until[q] = t + self.block_s
            self.blocks.append((t, int(q)))
        gone = flag | (self.blocked_until[p] > t)
        dels = fids[gone]
        n_after = n - int(gone.sum())
        if n_after / cap >= self.h_crit:
            eleph = _elephants(obs["bytes"])
            rest = np.flatnonzero(~gone & ~eleph)
            rest = rest[np.argsort(-s[rest], kind="stable")]
            dels = np.r_[dels, fids[rest[:n_after - int(self.target * cap)]]]
        return dels, None


def _key(det, budget, rule):
    return f"eb-{det}-b{budget:g}-n{rule[0]}f{rule[1]:g}"


def _parse(name):
    _, det, b, nf = name.split("-")
    n, f = nf[1:].split("f")
    return det, float(b[1:]), (int(n), float(f))


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
    if name == "none":
        return Defense()
    if name in ("v2.1+pg", "dms-blocklist"):
        return FH._make(name, d)
    det, b, (n_min, f_min) = _parse(name)
    dg = FH._dg(d)
    model, fidx = (_C["ens"], None) if det == "ens" else (dg.model, dg.feature_idx)
    return EvictBlock(model, _C["thr"][(det, b, d)], feature_idx=fidx, name=name, rho=dg.rho,
                      h_crit=dg.h_crit, target=dg.target, n_min=n_min, f_min=f_min)


def _episode(args):
    stage, name, d, v, s = args
    att = None if v == "benign" else attack_variant(v)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], att, s, FH.CFG.duration,
                                    FH.CFG.attack_start), "dedicated")
    df = _make(name, d)
    r = run_episode(tr, FH.CFG, df, record_ts=False).summary
    blocks = getattr(df, "blocks", [])
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
    names = [_key(det, b, r) for det in ("ens", "mlp") for b in BUDGETS for r in BLOCK_RULES]
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
    defs = ["none", "v2.1+pg", "dms-blocklist"] + [x for x in sel.values() if x]
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
