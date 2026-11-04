"""Fair eviction: PortGuard's per-port fair share used to pick eviction victims instead of
refusing new flows (follow-up to flashgate).

PortGuard beats E9's adaptive attacker by refusing new flows of ports over their fair share,
which also refuses benign flash crowds (4x crowd: 14.7 % harm). Switch eviction admits crowds
(2.0 %) but evicts the entries nearest idle expiry, which a fast-refreshing attacker never is
(E9 worst 20 %). Fair eviction keeps admission open and, when the table is full, evicts from the
port furthest over its fair share: max-min over ports, equal or weighted by each port's entries
in calm polls (as PortGuard's weighted share). Within a port it evicts either the entry nearest
idle expiry (as OVS) or the lowest packet rate first, with entries younger than min_age last
(a crowd's new flows are young; an overflow attack's entries live for minutes). DualGuard v2.1
runs unchanged inside.

select  share {equal, weighted} x order {expiry, rate with min_age 2 s, rate with min_age 5 s}
        on validation seeds 2000-2002, D1-D3, dedicated ports, flashgate's cells (flash 2x and 4x
        without attack, flash 2x + A2, A1-A7, E9's three selected attacks, benign). Eligible: E9
        worst attack's mean harm <= v2.1 + PortGuard's + 0.5 points and A1-A7 mean harm <= v2.1 +
        PortGuard's + 0.25 points. Among eligible: lowest mean harm over the flash cells (ties
        within 0.05 points: equal before weighted, then expiry before rate, then smaller
        min_age). None eligible: report and stop.
test    v2.1, v2.1 + eviction, v2.1 + PortGuard and the selection on fresh seeds 23000-23009.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.fairevict --stages prereg,select,test,report

Writes results/fairevict/.
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

from . import flashgate as G
from . import flowhold as FH
from . import revision1 as R1
from . import sweeps as SW
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import Defense, weighted_level
from .e9_adaptive import ATTACKS as E9_ATTACKS
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/fairevict"
CFG = SimConfig(duration=300.0)
DOMS = ["D1", "D2", "D3"]
TEST_SEEDS = list(range(23000, 23010))
PG = "v2.1+pg"
GRID = [("equal", "expiry", 0.0), ("equal", "rate", 2.0), ("equal", "rate", 5.0),
        ("weighted", "expiry", 0.0), ("weighted", "rate", 2.0), ("weighted", "rate", 5.0)]
HARM_MARGIN, E9_MARGIN = 0.0025, 0.005
HYPOTHESES = dict(
    FE1="flash crowds: over flash 2x and 4x without attack and flash 2x + A2, fair eviction harms "
        "fewer benign flows than v2.1 + PortGuard (paired cluster Wilcoxon over domain x seed, "
        "Holm over FE1 and FE3's test)",
    FE2="adaptive: fair eviction's worst E9 attack mean harm is <= v2.1 + PortGuard's + 0.5 points",
    FE3="A1-A7: fair eviction is non-inferior to v2.1 + PortGuard (cluster bootstrap 95 % upper "
        "bound of the mean harm difference <= 0.5 points)",
    FE4="descriptive: flash harm of fair eviction against v2.1 + eviction",
)


class FairEvict(Defense):
    """Wraps a defense; on a full table evicts from the port furthest over its fair share."""
    evict_needs_install = True

    def __init__(self, inner, share="equal", order="expiry", min_age=2.0, calm=0.7, tau_s=60.0,
                 name="fairevict"):
        self.inner, self.share, self.order, self.min_age = inner, share, order, min_age
        self.calm, self.tau_s, self.name = calm, tau_s, name
        self.needs_features = inner.needs_features
        f = getattr(inner, "admit_filter", None)
        if f is not None:
            self.admit_filter = f
        self.evict_on_full = self._evict

    def reset(self, ctx):
        self.inner.reset(ctx)
        self.port = ctx["flow_port"]
        if self.port is None:
            raise ValueError("FairEvict needs traffic.flow_port (see ports.assign_ports)")
        self.np = int(self.port.max()) + 1
        self.base = np.zeros(self.np)
        self.bn = 0
        self.cap = None
        self.rate = np.full(ctx["n_flows"], np.inf)      # packets/s at the last poll

    def admit_timeouts(self, fids, now, default):
        return self.inner.admit_timeouts(fids, now, default)

    def on_poll(self, t, obs):
        self.cap = obs["capacity"]
        f = obs["fids"]
        if len(f):
            self.rate[f] = obs["pkts"] / np.maximum(t - obs["install_t"], 1.0)
        if obs["count"] / obs["capacity"] < self.calm:
            c = np.bincount(self.port[f], minlength=self.np).astype(float)
            self.bn += 1
            a = max(1.0 - np.exp(-1.0 / self.tau_s), 1.0 / self.bn)
            self.base += a * (c - self.base)
        return self.inner.on_poll(t, obs)

    def _victims_per_port(self, c, n):
        if self.share == "equal":
            w = np.ones(self.np)
        else:
            w = np.maximum(self.base, 0.01 * (self.cap or c.sum()) / self.np)
        lam = weighted_level(c, w, c.sum() - n)
        keep = np.minimum(c, np.floor(w * lam)) if np.isfinite(lam) else c.copy()
        v = c - keep
        short = n - int(v.sum())
        while short > 0:                       # rounding: take from the ports most over share
            over = np.where(c - v > 0, (c - v) / w, -np.inf)
            p = int(np.argmax(over))
            v[p] += 1
            short -= 1
        return v.astype(int)

    def _evict(self, n_needed, cand, last_seen, idle_to, now, install_t):
        n = min(n_needed, len(cand))
        if n <= 0:
            return cand[:0]
        p = self.port[cand]
        v = self._victims_per_port(np.bincount(p, minlength=self.np).astype(float), n)
        out = []
        for q in np.flatnonzero(v):
            sel = cand[p == q]
            if self.order == "expiry":
                key = last_seen[sel] + idle_to[sel] - now
            else:
                young = (now - install_t[sel]) < self.min_age
                key = np.where(young, 1e9 - (now - install_t[sel]), self.rate[sel])
            out.append(sel[np.argsort(key, kind="stable")[:v[q]]])
        return np.concatenate(out)


def _key(share, order, min_age):
    return f"fe-{share}-{order}" + (f"{min_age:g}" if order == "rate" else "")


def _candidates():
    return [_key(*g) for g in GRID]


def _make(name, d):
    if name.startswith("fe-"):
        share, order = name.split("-")[1:3]
        min_age = float(order[4:]) if order.startswith("rate") else 0.0
        return FairEvict(FH._dg(d), share=share, order="rate" if order.startswith("rate") else "expiry",
                         min_age=min_age, name=name)
    return G._make(name, d)


def _episode(args):
    stage, name, traffic, d, v, s = args
    prof = SW._flash(d, int(traffic[-1])) if traffic != "normal" else DOMAINS[d]
    att = None if v == "benign" else (VARIANTS.get(v) or E9_ATTACKS[v])
    tr = assign_ports(build_traffic(prof, DOMAIN_IDX[d], att, s, CFG.duration, CFG.attack_start),
                      "dedicated")
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(stage=stage, defense=name, traffic=traffic, domain=d, variant=v, seed=s,
                cell=f"{traffic}/{v}", flow_mods=r["installs"] + r["deletes"] + r["demotes"], **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), domains=DOMS, candidates=_candidates(),
        reference=PG, val_seeds=list(SPLITS["val"]), test_seeds=TEST_SEEDS,
        cells=[f"{a}/{b}" for a, b in G._cells()], e9_attacks=G.E9_ATT(), scenario="dedicated",
        selection=f"eligible: E9 worst mean harm <= {PG} + {E9_MARGIN} and A1-A7 mean harm <= "
                  f"{PG} + {HARM_MARGIN}; among eligible, lowest mean harm over {G.FLASH}; ties "
                  "within 0.0005: equal before weighted, expiry before rate, smaller min_age; "
                  "none eligible: report, no test",
        test_defenses=["v2.1", "v2.1+evict", PG, "<selected>"], hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    if not os.path.exists(path):
        FH._load()
        tasks = [("select", n, tr, d, v, s) for n in [PG, "v2.1+evict"] + _candidates()
                 for d in DOMS for tr, v in G._cells() for s in SPLITS["val"]]
        _run(tasks, workers, "select").to_csv(path, index=False)
    df = pd.read_csv(path)
    df["group"] = G._groups(df)
    m = df.groupby(["defense", "group"]).benign_flows_harmed_frac.mean().unstack()
    e9w = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean() \
        .groupby("defense").max()
    rows = []
    for i, c in enumerate([PG, "v2.1+evict"] + _candidates()):
        ok = bool(e9w[c] <= e9w[PG] + E9_MARGIN and m.loc[c, "A1-A7"] <= m.loc[PG, "A1-A7"] + HARM_MARGIN)
        rows.append(dict(defense=c, flash_pct=round(100 * m.loc[c, "flash"], 3),
                         a1_a7_pct=round(100 * m.loc[c, "A1-A7"], 3), e9_worst_pct=round(100 * e9w[c], 2),
                         benign_pct=round(100 * m.loc[c, "benign"], 3),
                         flow_mods=round(df[df.defense == c].flow_mods.mean()),
                         eligible=ok and c.startswith("fe-"), tb=i))
    t = pd.DataFrame(rows)
    ok = t[t.eligible]
    sel = ok[ok.flash_pct <= ok.flash_pct.min() + 0.05].sort_values("tb").defense.iloc[0] if len(ok) else None
    t.drop(columns="tb").to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel))
    pd.set_option("display.width", 250)
    print(t.drop(columns="tb").to_string(index=False))
    print("selected", sel)


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    if sel is None:
        print("no candidate eligible; no test")
        return
    FH._load()
    tasks = [("test", n, tr, d, v, s) for n in ["v2.1", "v2.1+evict", PG, sel] for d in DOMS
             for tr, v in G._cells() for s in TEST_SEEDS]
    _run(tasks, workers, "test").to_csv(path, index=False)


def stage_report():
    path = os.path.join(OUT, "test_episodes.csv")
    if not os.path.exists(path):
        print("no test episodes")
        return
    df = pd.read_csv(path)
    sel = json.load(open(os.path.join(OUT, "selected.json")))["selected"]
    df["group"] = G._groups(df)
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    rows = []
    for (n, g), h in df.groupby(["defense", "group"]):
        rows.append(dict(defense=n, group=g, harmed=R1._fmt(h, "benign_flows_harmed_frac"),
                         attack_share=round(100 * h.avg_attack_occ_post.mean(), 2),
                         overflow_s=round(h.overflow_seconds_post_attack.mean(), 2),
                         flow_mods=int(h.flow_mods.mean()), packet_in=int(h.packet_in.mean())))
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "summary.csv"), index=False)
    piv = (df.pivot_table(index="defense", columns="cell", values="benign_flows_harmed_frac") * 100).round(2)
    piv.to_csv(os.path.join(tdir, "harm_by_cell.csv"))
    tests = []
    for hyp, grp in (("FE1", "flash"), ("FE3", "A1-A7")):
        md, w, l, p = R1.cluster_wilcoxon(df[df.group == grp], "benign_flows_harmed_frac", sel, PG)
        tests.append(dict(hyp=hyp, a=sel, b=PG, mean_diff=md, a_lower=w, a_higher=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    a = df[df.group == "A1-A7"].set_index(["defense", "domain", "variant", "seed"]).benign_flows_harmed_frac
    d = a.loc[sel] - a.loc[PG].reindex(a.loc[sel].index)
    up = FH._boot_upper(d.values, np.array([f"{i[0]}|{i[2]}" for i in d.index]))
    e = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()
    fl = df[df.group == "flash"].groupby("defense").benign_flows_harmed_frac.mean()
    fe1 = t[t.hyp == "FE1"].iloc[0]
    verdict = dict(FE1=bool(fe1.p_holm < 0.05 and fe1.mean_diff < 0),
                   FE2=bool(e.loc[sel].max() <= e.loc[PG].max() + E9_MARGIN), FE3=bool(up <= 0.005))
    summ = dict(selected=sel, verdict=verdict, e9_worst_sel=round(100 * e.loc[sel].max(), 2),
                e9_worst_pg=round(100 * e.loc[PG].max(), 2), a1_a7_diff=round(100 * float(d.mean()), 3),
                a1_a7_upper95=round(100 * up, 3), flash={k: round(100 * v, 2) for k, v in fl.items()})
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    _dump(OUT, "verdict.json", summ)
    pd.set_option("display.width", 300)
    print(pd.DataFrame(rows).to_string(index=False))
    print(piv.T.to_string())
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
