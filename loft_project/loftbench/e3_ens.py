"""Simulator check of the ensemble on development (validation) seeds, before any testbed run.

Model: RF (50 trees, depth 12) + CatBoost, each federated by model sharing (mean of the
controllers' local models), combined by soft voting. Two thresholds per controller from its
benign validation scores: tau at the 1 % budget, tau_h at the stricter HARD_BUDGET.
Two-tier policy (TwoTierGuard): score >= tau_h: demote (delete now, short idle timeout on
reinstall), as DualGuard; tau <= score < tau_h: soft, no delete, the flow only gets the short
idle timeout from its next install. Each defense runs inside PortGuard as the final system does.

Defenses: none; v2.1+pg (the frozen system's MLP); ens+pg (ensemble, two tiers);
ens1+pg (ensemble, one tier: demote at tau, isolates the tier rule); cb+pg (CatBoost alone,
two tiers, the single-model alternative). Domains D1-D3; A2, A4, E9P, A6 (unseen by every
controller) and benign; validation seeds 2000-2002. Development data only: no test seeds.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e3_ens [--workers 4]

Writes results/e3_ens/{models.pkl, episodes.csv, summary.csv}.
"""
import argparse
import os
import pickle
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import flowhold as FH
from . import ml_compare as M
from . import revision5 as R5
from .config import DOMAINS, attack_variant
from .data import DOMAIN_IDX
from .defenses import Defense, DualGuard, PortGuard
from .e1_pair import RF, _fit, _rf
from .e1_subsets import _make as _tree
from .experiment import SPLITS
from .models import threshold_at_fpr
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/e3_ens"
DOMS = ["D1", "D2", "D3"]
VARS = ["A2", "A4", "E9P", "A6", "benign"]
DEFS = ["none", "v2.1+pg", "ens+pg", "ens1+pg", "cb+pg"]
HARD_BUDGET = 0.005
_C = {}


class TwoTierGuard(DualGuard):
    """DualGuard whose demotion needs score >= tau_h; tau <= score < tau_h only marks the flow
    for the short idle timeout at its next install (no delete, no extra Packet-In)."""

    def __init__(self, model, tau, tau_h, **kw):
        super().__init__(model, tau, **kw)
        self.tau_h = tau_h

    def on_poll(self, t, obs):
        cap, n = obs["capacity"], obs["count"]
        if n == 0 or n / cap < self.rho:
            return None, None
        s = self.model.predict_proba(obs["X"])
        soft = (s >= self.tau) & (s < self.tau_h)
        self.demoted[obs["fids"][soft]] = True
        hard = s >= self.tau_h
        dems = obs["fids"][hard]
        self.demoted[dems] = True
        dels = None
        n_after = n - int(hard.sum())
        if self.hard and n_after / cap >= self.h_crit:
            eleph = _elephants(obs["bytes"])
            rest = np.flatnonzero(~hard & ~eleph)
            rest = rest[np.argsort(-s[rest], kind="stable")]
            dels = obs["fids"][rest[:n_after - int(self.target * cap)]]
        return dels, dems


def _elephants(b):
    from .defenses import _elephants as e
    return e(b)


def _models():
    path = os.path.join(OUT, "models.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tr = {d: data[("train", d)] for d in DOMAINS}
    rf, _ = _fit(lambda: _rf(RF["rf50d12"]), tr)
    cb, _ = _fit(lambda: _tree("cb"), tr)
    ens = M.Mean([rf, cb])
    taus = {}
    for d in DOMS:
        v = data[("val", d)]
        for k, m in (("ens", ens), ("cb", cb)):
            sb = m.predict_proba(v.X[v.y == 0])
            taus[(k, d)] = (threshold_at_fpr(sb, M.BUDGET), threshold_at_fpr(sb, HARD_BUDGET))
    out = dict(ens=ens, cb=cb, taus=taus)
    pickle.dump(out, open(path, "wb"))
    return out


def _make(name, d):
    if name == "none":
        return Defense()
    if name == "v2.1+pg":
        return FH._make("v2.1+pg", d)
    base = FH._dg(d)                      # the frozen system's policy knobs (rho, t_short, hard)
    kw = dict(rho=base.rho, t_short=base.t_short, hard=base.hard, h_crit=base.h_crit,
              target=base.target)
    fam = "cb" if name.startswith("cb") else "ens"
    tau, tau_h = _C["taus"][(fam, d)]
    if name == "ens1+pg":
        inner = DualGuard(_C["ens"], tau, name="ens1", **kw)
    else:
        inner = TwoTierGuard(_C[fam], tau, tau_h, name=fam, **kw)
    P = R5._CTX["P"]
    return PortGuard(inner, name=name, **{x: P[x] for x in ("mode", "share", "q", "rho_q",
                                                            "hold_s", "tau_s")})


def _episode(args):
    name, d, v, s = args
    att = None if v == "benign" else attack_variant(v)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], att, s, FH.CFG.duration,
                                    FH.CFG.attack_start), "dedicated")
    r = run_episode(tr, FH.CFG, _make(name, d), record_ts=False).summary
    return dict(defense=name, domain=d, variant=v, seed=s, **r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    _C.update(_models())
    print("  models ready", {k: tuple(round(x, 4) for x in v) for k, v in _C["taus"].items()}, flush=True)
    FH._load()
    tasks = [(n, d, v, s) for n in DEFS for d in DOMS for v in VARS for s in SPLITS["val"]]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(a.workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=1)):
            rows.append(row)
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "episodes.csv"), index=False)
    cols = {"benign_flows_harmed_frac": "harm_pct", "benign_flows_impacted_frac": "impact_pct",
            "avg_attack_occ_post": "attack_occ_pct"}
    tab = df.groupby(["variant", "defense"])[list(cols)].mean().rename(columns=cols) * 100
    tab["demotes"] = df.groupby(["variant", "defense"]).demotes.mean()
    tab["benign_demotes"] = df.groupby(["variant", "defense"]).benign_demotes.mean() \
        if "benign_demotes" in df else np.nan
    tab = tab.round(2)
    tab.to_csv(os.path.join(OUT, "summary.csv"))
    pd.set_option("display.width", 200)
    print(tab.to_string())


if __name__ == "__main__":
    main()
