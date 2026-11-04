"""PortGuard trigger that tells benign flash crowds from attacks (follow-up to E8 and fgpg).

Under a benign 4x flash crowd v2.1 + PortGuard harms 13.9 % of benign flows (E8), because once
the table passes rho_q PortGuard holds it at q x capacity and refuses the crowd's new flows,
while switch eviction would let them in (v2.1 + eviction: 1.7 %, evict_fallback). A crowd's new
flows come from many sources and spread over all benign ports; an attack's growth sits on the
attacker's ports. So the gate enforces PortGuard only when, besides occupancy >= rho_q, the
growth over each port's calm baseline is concentrated:

    skew = max_p g_p / sum_p max(g_p, 0),   g_p = entries_p - baseline_p

baseline_p is an exponential average (time constant tau) of port p's entries over polls below
rho_q. With the gate closed, overflow falls through to switch eviction when evict is on.

select  v2.1 + PortGuard (revision 4b knobs) gated at skew >= {0.35, 0.5, 0.65} x tau {60, 300}
        x evict {off, on}, plus ungated with eviction, on validation seeds 2000-2002, D1-D3,
        dedicated ports, cells: flash 2x and 4x without attack, flash 2x + A2, A1-A7, E9's three
        selected attacks, benign. Eligible: E9 worst attack's mean harm <= base's + 0.5 points
        and A1-A7 mean harm <= base's + 0.25 points. Among eligible: lowest mean harm over the
        three flash cells (ties within 0.05 points: higher skew threshold, then evict off, then
        longer tau). None eligible: no gate.
test    base, selected, v2.1 and v2.1 + eviction on fresh seeds 22000-22009, same cells, one shot.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.flashgate --stages prereg,select,test,report

Writes results/flashgate/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import itertools
import json
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import e9_adaptive as E9
from . import flowhold as FH
from . import revision1 as R1
from . import revision5 as R5
from . import sweeps as SW
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import OVSEvict, PortGuard
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/flashgate"
CFG = SimConfig(duration=300.0)
DOMS = ["D1", "D2", "D3"]
TEST_SEEDS = list(range(22000, 22010))
BASE = "v2.1+pg"
GRID = dict(skew=[0.35, 0.5, 0.65], tau=[60.0, 300.0], evict=[False, True])
FLASH = ["flash2/benign", "flash4/benign", "flash2/A2"]
HARM_MARGIN, E9_MARGIN = 0.0025, 0.005
HYPOTHESES = dict(
    FC1="flash crowds: over flash 2x and 4x without attack and flash 2x + A2, the selected gate "
        "harms fewer benign flows than v2.1 + PortGuard (paired cluster Wilcoxon over domain x "
        "seed, Holm over FC1 and FC3's test)",
    FC2="adaptive: the selected gate's worst E9 attack mean harm is <= v2.1 + PortGuard's + 0.5 "
        "points",
    FC3="A1-A7: the selected gate is non-inferior to v2.1 + PortGuard (cluster bootstrap 95 % "
        "upper bound of the mean harm difference <= 0.5 points)",
    FC4="descriptive: flash harm of the selected gate against v2.1 + eviction",
)
_M = {}


class SkewGatePortGuard(PortGuard):
    """PortGuard that starts enforcing only when the table's growth is concentrated on a port."""

    def __init__(self, inner=None, skew=0.5, tau=60.0, **kw):
        super().__init__(inner, **kw)
        self.skew_min, self.gate_tau = skew, tau

    def reset(self, ctx):
        super().reset(ctx)
        self.gbase = np.zeros(len(self.quota))
        self.gn = 0
        self.skew_log = []

    def _open(self, t, obs):
        c = np.bincount(self.port[obs["fids"]], minlength=len(self.gbase)).astype(float)
        if obs["count"] / obs["capacity"] < self.rho_q:
            self.gn += 1
            a = max(1.0 - np.exp(-1.0 / self.gate_tau), 1.0 / self.gn)
            self.gbase += a * (c - self.gbase)
            return False
        g = np.maximum(c - self.gbase, 0)
        skew = g.max() / g.sum() if g.sum() > 0 else 0.0
        self.skew_log.append(skew)
        return skew >= self.skew_min

    def on_poll(self, t, obs):
        if self._open(t, obs):
            return super().on_poll(t, obs)
        rho, self.rho_q = self.rho_q, np.inf       # gate closed: no new enforcement this poll
        try:
            return super().on_poll(t, obs)
        finally:
            self.rho_q = rho


def _key(skew, tau, evict):
    return f"gate{skew:g}t{tau:g}" + ("+evict" if evict else "")


def _candidates():
    return [f"{BASE}|{_key(*c)}" for c in itertools.product(*GRID.values())] + [f"{BASE}+evict"]


def _make(name, d):
    if name == "v2.1":
        return FH._make("v2.1", d)
    if name == "v2.1+evict":
        df = FH._make("v2.1", d)
        df.evict_on_full, df.name = OVSEvict._evict, name
        return df
    P = {x: R5._CTX["P"][x] for x in ("mode", "share", "q", "rho_q", "hold_s", "tau_s")}
    if name == BASE:
        return FH._make(BASE, d)
    if name == f"{BASE}+evict":
        df = FH._make(BASE, d)
    else:
        g = name.split("|")[1]
        skew, tau = g[4:].removesuffix("+evict").split("t")
        df = SkewGatePortGuard(FH._dg(d), skew=float(skew), tau=float(tau), name=name, **P)
    if name.endswith("+evict"):
        df.evict_on_full = OVSEvict._evict
    df.name = name
    return df


def _cells():
    c = [tuple(x.split("/")) for x in FLASH]
    c += [("normal", v) for v in list(VARIANTS) + E9_ATT()] + [("normal", "benign")]
    return c


def E9_ATT():
    return sorted({b["attack"] for b in json.load(open(os.path.join(E9.OUT, "selected.json"))).values()})


def _episode(args):
    stage, name, traffic, d, v, s = args
    prof = SW._flash(d, int(traffic[-1])) if traffic != "normal" else DOMAINS[d]
    att = None if v == "benign" else (VARIANTS.get(v) or E9.ATTACKS[v])
    tr = assign_ports(build_traffic(prof, DOMAIN_IDX[d], att, s, CFG.duration, CFG.attack_start),
                      "dedicated")
    df = _make(name, d)
    r = run_episode(tr, CFG, df, record_ts=False).summary
    sk = getattr(df, "skew_log", [])
    return dict(stage=stage, defense=name, traffic=traffic, domain=d, variant=v, seed=s,
                cell=f"{traffic}/{v}", skew_mean=float(np.mean(sk)) if sk else np.nan,
                flow_mods=r["installs"] + r["deletes"] + r["demotes"], **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def _groups(df):
    return np.select([df.cell.isin(FLASH), df.variant.isin(VARIANTS) & (df.traffic == "normal"),
                      df.variant.isin(E9_ATT())], ["flash", "A1-A7", "E9"], "benign")


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=DOMS, grid=GRID, base=BASE,
        candidates=_candidates(), val_seeds=list(SPLITS["val"]), test_seeds=TEST_SEEDS,
        cells=[f"{a}/{b}" for a, b in _cells()], e9_attacks=E9_ATT(), scenario="dedicated",
        selection=f"eligible: E9 worst mean harm <= base + {E9_MARGIN} and A1-A7 mean harm <= "
                  f"base + {HARM_MARGIN}; among eligible, lowest mean harm over {FLASH}; ties "
                  f"within 0.0005: higher skew, then evict off, then longer tau; none: no gate",
        test_defenses=["v2.1", "v2.1+evict", BASE, "<selected>"], hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    if not os.path.exists(path):
        FH._load()
        tasks = [("select", n, tr, d, v, s) for n in [BASE] + _candidates() for d in DOMS
                 for tr, v in _cells() for s in SPLITS["val"]]
        _run(tasks, workers, "select").to_csv(path, index=False)
    df = pd.read_csv(path)
    df["group"] = _groups(df)
    m = df.groupby(["defense", "group"]).benign_flows_harmed_frac.mean().unstack()
    e9w = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean() \
        .groupby("defense").max()
    rows = []
    for c in [BASE] + _candidates():
        ok = bool(e9w[c] <= e9w[BASE] + E9_MARGIN and m.loc[c, "A1-A7"] <= m.loc[BASE, "A1-A7"] + HARM_MARGIN)
        g = c.split("|")[1] if "|" in c else ""
        skew = float(g[4:].removesuffix("+evict").split("t")[0]) if g else 1.0
        tau = float(g[4:].removesuffix("+evict").split("t")[1]) if g else 0.0
        rows.append(dict(defense=c, flash_pct=round(100 * m.loc[c, "flash"], 3),
                         a1_a7_pct=round(100 * m.loc[c, "A1-A7"], 3), e9_worst_pct=round(100 * e9w[c], 2),
                         benign_pct=round(100 * m.loc[c, "benign"], 3), eligible=ok and c != BASE,
                         tb=(-skew, c.endswith("+evict"), -tau)))
    t = pd.DataFrame(rows)
    ok = t[t.eligible]
    if len(ok):
        near = ok[ok.flash_pct <= ok.flash_pct.min() + 0.05]
        sel = near.sort_values("tb").defense.iloc[0]
    else:
        sel = BASE
    t.drop(columns="tb").to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel))
    pd.set_option("display.width", 250)
    print(t.drop(columns="tb").to_string(index=False))
    print("selected", sel)


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    FH._load()
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    names = list(dict.fromkeys(["v2.1", "v2.1+evict", BASE, sel]))
    tasks = [("test", n, tr, d, v, s) for n in names for d in DOMS for tr, v in _cells()
             for s in TEST_SEEDS]
    _run(tasks, workers, "test").to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    df["group"] = _groups(df)
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    rows = []
    for (n, g), h in df.groupby(["defense", "group"]):
        rows.append(dict(defense=n, group=g, harmed=R1._fmt(h, "benign_flows_harmed_frac"),
                         attack_share=round(100 * h.avg_attack_occ_post.mean(), 2),
                         overflow_s=round(h.overflow_seconds_post_attack.mean(), 2),
                         flow_mods=int(h.flow_mods.mean())))
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "summary.csv"), index=False)
    piv = (df.pivot_table(index="defense", columns="cell", values="benign_flows_harmed_frac") * 100).round(2)
    piv.to_csv(os.path.join(tdir, "harm_by_cell.csv"))
    sk = df.pivot_table(index="defense", columns="cell", values="skew_mean").round(3)
    sk.to_csv(os.path.join(tdir, "skew_by_cell.csv"))
    pd.set_option("display.width", 300)
    print(pd.DataFrame(rows).to_string(index=False))
    print(piv.T.to_string())
    print(sk.T.to_string())
    if sel == BASE:
        print("no gate selected; nothing to test")
        return
    tests = []
    for hyp, grp in (("FC1", "flash"), ("FC3", "A1-A7")):
        md, w, l, p = R1.cluster_wilcoxon(df[df.group == grp], "benign_flows_harmed_frac", sel, BASE)
        tests.append(dict(hyp=hyp, a=sel, b=BASE, mean_diff=md, a_lower=w, a_higher=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    a = df[df.group == "A1-A7"].set_index(["defense", "domain", "variant", "seed"]).benign_flows_harmed_frac
    d = a.loc[sel] - a.loc[BASE].reindex(a.loc[sel].index)
    up = FH._boot_upper(d.values, np.array([f"{i[0]}|{i[2]}" for i in d.index]))
    e = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()
    fl = df[df.group == "flash"].groupby("defense").benign_flows_harmed_frac.mean()
    fc1 = t[t.hyp == "FC1"].iloc[0]
    verdict = dict(FC1=bool(fc1.p_holm < 0.05 and fc1.mean_diff < 0),
                   FC2=bool(e.loc[sel].max() <= e.loc[BASE].max() + E9_MARGIN),
                   FC3=bool(up <= 0.005))
    summ = dict(selected=sel, verdict=verdict, e9_worst_sel=round(100 * e.loc[sel].max(), 2),
                e9_worst_base=round(100 * e.loc[BASE].max(), 2), a1_a7_diff=round(100 * float(d.mean()), 3),
                a1_a7_upper95=round(100 * up, 3),
                flash={k: round(100 * v, 2) for k, v in fl.items()})
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    _dump(OUT, "verdict.json", summ)
    print(t.round(5).to_string(index=False))
    print(json.dumps(summ, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("select", lambda: stage_select(a.workers)),
                     ("test", lambda: stage_test(a.workers)), ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
