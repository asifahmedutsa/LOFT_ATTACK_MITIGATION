"""Churn quarantine for fair eviction: cut the controller load of evicted entries that return.

On the testbed (results/testbed_fe) fair eviction kept benign harm lowest, but under E9's adaptive
fast-refresh attack the attacker's evicted entries came straight back as Packet-Ins, each
reinstall evicted another attacker entry, and the saturated Ryu controller then failed to answer
the first packet of 30.5 % of benign flows (19 % with PortGuard). The simulator predicted the
churn: 217k flow-mods per episode against PortGuard's 45k.

Quarantine: per port, count the entries fair eviction evicts and those that come back (a Packet-In
for an evicted flow within RETURN_S). Under fair eviction alone (validation seeds 2000-2001, D1-D3,
feq_signal exploration) a benign port never had more than 114 returns in 10 s (4x flash crowd)
while every attacker port over its share had 1,595-10,035. A port with, over the last WINDOW_S,
>= r_min returns and a return ratio >= theta is quarantined: all its new flows are refused and its
entries are deleted at each poll (on the switch, one delete matching the host's MAC), so its
returns stop evicting each other and the table is left to benign flows. It stays quarantined while it keeps requesting refused flows at >= r_min per WINDOW_S, and
for at least hold_s after it stops. (A first version released after a fixed hold and refused only
above the fair share; on one validation seed the released attacker then evicted benign entries,
whose returns quarantined benign ports. A second kept the quarantined port's entries; they stayed
refreshed at 36 % of the table, DualGuard stayed active and demoted 10,994 benign flows.) On the testbed a refusal installs PortGuard's 2 s
per-host drop rule, so the refused host's packets stop at the switch, and the rule's packet count
gives the refused-request rate. Outside quarantine nothing changes: admission stays open and fair
eviction picks the victims.

select  theta {0.5, 0.8} x r_min {150, 300} x hold_s {10, 30} on validation seeds 2000-2002, D1-D3,
        dedicated ports, fairevict's cells. Eligible: flash mean harm <= fair eviction's + 0.25
        points, E9 worst attack's mean harm <= fair eviction's + 0.5 points, A1-A7 mean harm <=
        fair eviction's + 0.25 points. Among eligible: fewest mean controller messages under E9's
        attacks (installs + deletes + demotes + Packet-Ins that reach the controller, a refused
        port's packets counted once per drop-rule period), ties within 2 %: higher r_min, then
        higher theta, then shorter hold.
test    v2.1 + PortGuard, fair eviction and the selection on fresh seeds 24000-24009.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.fairevictq --stages prereg,select,test,report

Writes results/fairevictq/.

Round 2 (--round 2, results/fairevictq2/): round 1's selection (r_min 300, theta 0.8) never fired
on the testbed. The Ryu controller installs only about 150-200 flows/s in all, so an attacker's
evicted entries came back 50-120 times per 10 s, not the simulator's thousands, and only about
half of them within 10 s (median 4.9 s; the rest lost or delayed in the controller queue). The
thresholds are recalibrated to what both see, checked before this round on round 1's validation
data and on the earlier testbed runs (results/testbed_fe, seeds 4100-4102: plain fair eviction
and round 1): r_min {30, 60} x theta {0.3, 0.5}, hold 10 s. Every candidate catches all 30
attacker episodes on validation seeds and 76-81 % of attacker 10 s windows on the testbed,
against at most 1 of 2,092 benign simulator windows and 1 benign testbed window. Same cells,
eligibility, selection and hypotheses as round 1, fresh seeds 25000-25009.
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

from . import fairevict as F
from . import flashgate as G
from . import flowhold as FH
from . import revision1 as R1
from . import sweeps as SW
from .config import DOMAINS, VARIANTS
from .data import DOMAIN_IDX
from .e9_adaptive import ATTACKS as E9_ATTACKS
from .experiment import SPLITS, _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/fairevictq"
CFG = F.CFG
DOMS = ["D1", "D2", "D3"]
TEST_SEEDS = list(range(24000, 24010))
FE = "fe-weighted-expiry"                      # fair eviction as selected in results/fairevict
PG = "v2.1+pg"
RETURN_S, WINDOW_S, DROP_S = 10.0, 10.0, 2.0
GRID = list(itertools.product((0.5, 0.8), (150, 300), (10.0, 30.0)))
FLASH_MARGIN, E9_MARGIN, HARM_MARGIN = 0.0025, 0.005, 0.0025
HYPOTHESES = dict(
    FQ1="load: under E9's three attacks the selection sends fewer controller messages than fair "
        "eviction (paired cluster Wilcoxon over domain x seed), and at most half as many on "
        "average",
    FQ2="adaptive: the selection's worst E9 attack mean harm is <= fair eviction's + 0.5 points",
    FQ3="flash crowds: non-inferior to fair eviction (cluster bootstrap 95 % upper bound of the "
        "mean harm difference over the flash cells <= 0.5 points)",
    FQ4="A1-A7: non-inferior to fair eviction (same bound, <= 0.5 points)",
    FQ5="descriptive: controller messages and harm against v2.1 + PortGuard",
)


class QuarantineFairEvict(F.FairEvict):
    """Fair eviction that refuses ports whose evicted entries keep coming back."""

    def __init__(self, inner, theta=0.5, r_min=300, hold_s=30.0, share="weighted", name="feq"):
        super().__init__(inner, share=share, order="expiry", name=name)
        self.theta, self.r_min, self.hold_s = theta, r_min, hold_s
        self.admit_filter = self._admit

    def reset(self, ctx):
        super().reset(ctx)
        self.ev_t = np.full(ctx["n_flows"], -np.inf)   # time the flow was last evicted
        self.log = []               # (t, port, kind): 0 eviction, 1 return, 2 refused request
        self.q_until = np.zeros(self.np)
        self.drop_until = np.zeros(self.np)
        self.ctl_msgs = 0           # Packet-Ins reaching the controller (see _admit)
        self.q_events = 0
        self.port_del_entries = self.port_del_msgs = 0
        self.inner_admit = getattr(self.inner, "admit_filter", None)

    def note_evicted(self, fids, now):
        """Record evictions; the testbed calls this with the evictions its polls infer."""
        self.ev_t[fids] = now
        self.log.extend((now, int(p), 0) for p in self.port[fids])

    def note_refused(self, port, n, now):
        """The testbed's refused requests: packets its drop rule for the port's host matched."""
        self.log.extend((now, int(port), 2) for _ in range(int(n)))

    def _evict(self, n_needed, cand, last_seen, idle_to, now, install_t):
        v = cand[:0]
        qc = cand[self.q_until[self.port[cand]] > now]
        if len(qc):                 # a quarantined port's entries first, nearest idle expiry first
            v = qc[np.argsort(last_seen[qc] + idle_to[qc], kind="stable")[:n_needed]]
            n_needed -= len(v)
            if n_needed > 0:
                cand = np.setdiff1d(cand, v, assume_unique=True)
        if n_needed > 0:
            v = np.concatenate([v, super()._evict(n_needed, cand, last_seen, idle_to, now, install_t)])
        if len(v):
            self.note_evicted(v, now)
        return v

    def _admit(self, fids, now):
        ok = np.ones(len(fids), bool) if self.inner_admit is None else self.inner_admit(fids, now)
        p = self.port[fids]
        ret = now - self.ev_t[fids] < RETURN_S
        if ret.any():
            self.log.extend((now, int(q), 1) for q in p[ret])
            self.ev_t[fids[ret]] = -np.inf
        q = self.q_until[p] > now
        if q.any():
            ok &= ~q
            self.log.extend((now, int(x), 2) for x in p[q])
        # Controller messages: the Packet-In of each admitted flow, and of a refused flow only
        # while its port has no drop rule (one per DROP_S per port, as the testbed installs).
        self.ctl_msgs += int(ok.sum())
        for x in np.unique(p[~ok]):
            if now >= self.drop_until[x]:
                self.drop_until[x] = now + DROP_S
                self.ctl_msgs += 1
        return ok

    def on_poll(self, t, obs):
        lo = t - WINDOW_S
        self.log = [e for e in self.log if e[0] >= lo]
        if self.log:
            a = np.array(self.log)
            ev, rt, rf = (np.bincount(a[a[:, 2] == k, 1].astype(int), minlength=self.np)
                          for k in (0, 1, 2))
            hit = (rt >= self.r_min) & (rt >= self.theta * ev)
            q = self.q_until > t
            self.q_events += int((hit & ~q).sum())
            self.q_until[hit | (q & (rf >= self.r_min))] = t + self.hold_s
        dels, dems = super().on_poll(t, obs)
        # A quarantined port's entries are deleted (on the switch one delete matching the host's
        # MAC): left in place, its refreshed entries keep the table near DualGuard's trigger and
        # DualGuard then demotes benign flows (one validation seed: 10,994 benign demotes).
        qp = self.q_until > t
        if qp.any():
            f = obs["fids"][qp[self.port[obs["fids"]]]]
            if len(f):
                self.port_del_entries += len(f)
                self.port_del_msgs += len(np.unique(self.port[f]))
                dels = f if dels is None or not len(dels) else np.union1d(dels, f)
        return dels, dems


def _key(theta, r_min, hold_s):
    return f"feq{theta:g}r{r_min}h{hold_s:g}"


def _parse(name):
    th, rest = name[3:].split("r")
    r, h = rest.split("h")
    return float(th), int(r), float(h)


def _candidates():
    return [_key(*g) for g in GRID]


def _make(name, d):
    if name.startswith("feq"):
        theta, r_min, hold = _parse(name)
        return QuarantineFairEvict(FH._dg(d), theta=theta, r_min=r_min, hold_s=hold, name=name)
    return F._make(name, d)


def _episode(args):
    stage, name, traffic, d, v, s = args
    prof = SW._flash(d, int(traffic[-1])) if traffic != "normal" else DOMAINS[d]
    att = None if v == "benign" else (VARIANTS.get(v) or E9_ATTACKS[v])
    tr = assign_ports(build_traffic(prof, DOMAIN_IDX[d], att, s, CFG.duration, CFG.attack_start),
                      "dedicated")
    df = _make(name, d)
    r = run_episode(tr, CFG, df, record_ts=False).summary
    fm = r["installs"] + r["deletes"] + r["demotes"]
    # Controller messages: flow-mods (a port-wide delete is one message) and the Packet-Ins that
    # reach the controller (without quarantine, all of them).
    pi = getattr(df, "ctl_msgs", None)
    pi = r["packet_in"] if pi is None else pi + r["table_full"]
    pd_ = getattr(df, "port_del_entries", 0) - getattr(df, "port_del_msgs", 0)
    return dict(stage=stage, defense=name, traffic=traffic, domain=d, variant=v, seed=s,
                cell=f"{traffic}/{v}", flow_mods=fm, ctl_msgs=fm - pd_ + pi,
                q_events=getattr(df, "q_events", 0), **r)


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
        reference=FE, val_seeds=list(SPLITS["val"]), test_seeds=TEST_SEEDS,
        constants=dict(return_s=RETURN_S, window_s=WINDOW_S, drop_s=DROP_S),
        cells=[f"{a}/{b}" for a, b in G._cells()], e9_attacks=G.E9_ATT(), scenario="dedicated",
        selection=f"eligible: flash mean harm <= {FE} + {FLASH_MARGIN}, E9 worst mean harm <= "
                  f"{FE} + {E9_MARGIN}, A1-A7 mean harm <= {FE} + {HARM_MARGIN}; among eligible, "
                  "fewest mean controller messages over E9's attacks; ties within 2 %: higher "
                  "r_min, then higher theta, then shorter hold; none eligible: report, no test",
        test_defenses=[PG, FE, "<selected>"], hypotheses=HYPOTHESES, grid=GRID,
        testbed="then D1, A2 / E9P / F4, seeds 4100-4102 against results/testbed_fe; primary "
                "testbed measure: benign impact (harm + unanswered first packets) under E9P"))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_select(workers):
    path = os.path.join(OUT, "select_episodes.csv")
    if not os.path.exists(path):
        FH._load()
        tasks = [("select", n, tr, d, v, s) for n in [FE] + _candidates()
                 for d in DOMS for tr, v in G._cells() for s in SPLITS["val"]]
        _run(tasks, workers, "select").to_csv(path, index=False)
    df = pd.read_csv(path)
    df["group"] = G._groups(df)
    m = df.groupby(["defense", "group"]).benign_flows_harmed_frac.mean().unstack()
    e9w = df[df.group == "E9"].groupby(["defense", "variant"]).benign_flows_harmed_frac.mean() \
        .groupby("defense").max()
    msgs = df[df.group == "E9"].groupby("defense").ctl_msgs.mean()
    rows = []
    for c in [FE] + _candidates():
        ok = bool(m.loc[c, "flash"] <= m.loc[FE, "flash"] + FLASH_MARGIN
                  and e9w[c] <= e9w[FE] + E9_MARGIN
                  and m.loc[c, "A1-A7"] <= m.loc[FE, "A1-A7"] + HARM_MARGIN)
        th, rm, hd = _parse(c) if c.startswith("feq") else (0, 0, 0)
        rows.append(dict(defense=c, flash_pct=round(100 * m.loc[c, "flash"], 3),
                         a1_a7_pct=round(100 * m.loc[c, "A1-A7"], 3), e9_worst_pct=round(100 * e9w[c], 2),
                         benign_pct=round(100 * m.loc[c, "benign"], 3), e9_ctl_msgs=round(msgs[c]),
                         q_events_flash=round(df[(df.defense == c) & (df.group == "flash")].q_events.mean(), 2),
                         eligible=ok and c.startswith("feq"), theta=th, r_min=rm, hold=hd))
    t = pd.DataFrame(rows)
    ok = t[t.eligible]
    sel = None
    if len(ok):
        best = ok.e9_ctl_msgs.min()
        sel = ok[ok.e9_ctl_msgs <= 1.02 * best].sort_values(["r_min", "theta", "hold"],
                                                                  ascending=[False, False, True]) \
            .defense.iloc[0]
    t.to_csv(os.path.join(OUT, "select_summary.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel))
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
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
    tasks = [("test", n, tr, d, v, s) for n in [PG, FE, sel] for d in DOMS
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
                         flow_mods=int(h.flow_mods.mean()), ctl_msgs=int(h.ctl_msgs.mean()),
                         q_events=round(h.q_events.mean(), 2)))
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "summary.csv"), index=False)
    piv = (df.pivot_table(index="defense", columns="cell", values="benign_flows_harmed_frac") * 100).round(2)
    piv.to_csv(os.path.join(tdir, "harm_by_cell.csv"))
    e9 = df[df.group == "E9"]
    md, w, l, p = R1.cluster_wilcoxon(e9, "ctl_msgs", sel, FE)
    ms = e9.groupby("defense").ctl_msgs.mean()
    e = e9.groupby(["defense", "variant"]).benign_flows_harmed_frac.mean()

    def upper(grp):
        a = df[df.group == grp].set_index(["defense", "domain", "cell", "seed"]).benign_flows_harmed_frac
        d = a.loc[sel] - a.loc[FE].reindex(a.loc[sel].index)
        return float(d.mean()), FH._boot_upper(d.values, np.array([f"{i[0]}|{i[2]}" for i in d.index]))
    fl_d, fl_up = upper("flash")
    a_d, a_up = upper("A1-A7")
    verdict = dict(FQ1=bool(p < 0.05 and md < 0 and ms[sel] <= 0.5 * ms[FE]),
                   FQ2=bool(e.loc[sel].max() <= e.loc[FE].max() + E9_MARGIN),
                   FQ3=bool(fl_up <= 0.005), FQ4=bool(a_up <= 0.005))
    summ = dict(selected=sel, verdict=verdict,
                e9_ctl_msgs={k: int(v) for k, v in ms.items()},
                fq1=dict(mean_diff=md, sel_lower=w, sel_higher=l, p=p),
                e9_worst={k: round(100 * e.loc[k].max(), 2) for k in (PG, FE, sel)},
                flash_diff=round(100 * fl_d, 3), flash_upper95=round(100 * fl_up, 3),
                a1_a7_diff=round(100 * a_d, 3), a1_a7_upper95=round(100 * a_up, 3))
    _dump(OUT, "verdict.json", summ)
    pd.set_option("display.width", 300)
    print(pd.DataFrame(rows).to_string(index=False))
    print(piv.T.to_string())
    print(json.dumps(summ, indent=1, default=float))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--round", type=int, default=1)
    a = ap.parse_args()
    if a.round == 2:
        global OUT, GRID, TEST_SEEDS
        OUT, TEST_SEEDS = "results/fairevictq2", list(range(25000, 25010))
        GRID = list(itertools.product((0.3, 0.5), (30, 60), (10.0,)))
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
