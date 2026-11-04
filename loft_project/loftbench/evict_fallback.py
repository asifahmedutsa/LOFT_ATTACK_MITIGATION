"""Follow-up to E8: switch eviction as the overflow fallback under FL-DualGuard.

E8 found that under benign flash crowds (overflow with no attack) v2.1 harms about as much as no
defense, because it only removes entries its detector flags, while OVS eviction
(overflow_policy=evict: evict the entries closest to idle expiry) harms least. Here the switch
evicts on overflow underneath the controller's defense, with no other change and nothing tuned.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.evict_fallback --stages prereg,test,report

Cells: E8's flash crowds (2x and 4x without attack, 2x during A2), A1-A7 and benign at normal
load, and E9's three selected best-response attacks. D1-D3, dedicated ports, unused seeds
17000-17009. Writes results/evict_fallback/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import pandas as pd

from . import e2_baselines as E2
from . import e9_adaptive as E9
from . import revision1 as R1
from . import sweeps as SW
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import OVSEvict
from .experiment import _dump
from .ports import assign_ports
from .report import holm
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/evict_fallback"
SEEDS = list(range(17000, 17010))
DEFENSES = ["ovs-evict", "v2.1", "v2.1+evict", "v2.1+portguard", "v2.1+portguard+evict"]
CFG = SimConfig(duration=300.0)
HYPOTHESES = dict(
    HF1="benign flash crowds without attack (2x and 4x): v2.1+evict harms fewer benign flows "
        "than v2.1, and at most OVS eviction + 0.5 points",
    HF2="A1-A7 at normal load: v2.1+evict is non-inferior to v2.1 (<= 0.5 points)",
    HF3="E9's selected attacks: v2.1+portguard+evict's worst case is at most v2.1+portguard's "
        "+ 0.5 points",
)


def _cells():
    e9 = sorted({b["attack"] for b in json.load(open(os.path.join(E9.OUT, "selected.json"))).values()})
    c = [("flash2", None), ("flash4", None), ("flash2", "A2")]
    c += [("normal", v) for v in list(VARIANTS) + [None]]
    return c + [("normal", a) for a in e9]


def _make(name, d):
    base = name.replace("+evict", "")
    df = E2._make(base, d)
    if name.endswith("+evict"):
        df.evict_on_full = OVSEvict._evict
        df.name = name
    return df


def _episode(args):
    name, traffic, v, d, s = args
    prof = SW._flash(d, int(traffic[-1])) if traffic != "normal" else DOMAINS[d]
    att = None if v is None else (VARIANTS[v] if v in VARIANTS else E9.ATTACKS[v])
    tr = assign_ports(build_traffic(prof, DOMAIN_IDX[d], att, s, CFG.duration, CFG.attack_start),
                      "dedicated")
    r = run_episode(tr, CFG, _make(name, d), record_ts=False).summary
    return dict(defense=name, traffic=traffic, variant=v or "benign", domain=d, seed=s, **r)


def stage_prereg():
    path = os.path.join(OUT, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(OUT, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), defenses=DEFENSES, cells=_cells(),
        seeds=SEEDS, eviction="OVSEvict._evict (closest to idle expiry) on overflow, under the "
                              "unchanged defense; nothing selected or tuned",
        hypotheses=HYPOTHESES))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(OUT, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    E2._load()
    tasks = [(n, f, v, d, s) for n in DEFENSES for f, v in _cells() for d in DOMAINS for s in SEEDS]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [test] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    df["cell"] = df.traffic + "/" + df.variant
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    groups = {"flash, no attack": ["flash2/benign", "flash4/benign"], "flash2 + A2": ["flash2/A2"],
              "A1-A7": [f"normal/{v}" for v in VARIANTS], "benign": ["normal/benign"]}
    for a in sorted({c for c in df.cell if c.startswith("normal/t")}):
        groups[f"E9 {a[7:]}"] = [a]
    rows = []
    for g, cells in groups.items():
        h = df[df.cell.isin(cells)]
        for n in DEFENSES:
            x = h[h.defense == n]
            rows.append(dict(group=g, defense=n, harmed=R1._fmt(x, "benign_flows_harmed_frac"),
                             attack_share=round(100 * x.avg_attack_occ_post.mean(), 1),
                             overflow_s=round(x.overflow_seconds.mean(), 2)))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(tdir, "summary.csv"), index=False)
    piv = (100 * df.groupby(["cell", "defense"]).benign_flows_harmed_frac.mean()).unstack(1)[DEFENSES].round(2)
    piv.to_csv(os.path.join(tdir, "harm_by_cell.csv"))
    tests = []
    for g, cells in groups.items():
        h = df[df.cell.isin(cells)]
        for a, b in (("v2.1+evict", "v2.1"), ("v2.1+evict", "ovs-evict"),
                     ("v2.1+portguard+evict", "v2.1+portguard"), ("v2.1+portguard+evict", "ovs-evict")):
            md, w, l, p = R1.cluster_wilcoxon(h, "benign_flows_harmed_frac", a, b)
            tests.append(dict(group=g, a=a, b=b, mean_diff=md, a_lower=w, a_higher=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = holm(t.p.values)
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 250)
    print(piv.to_string())
    print(t.round(5).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prereg,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for name, fn in (("prereg", stage_prereg), ("test", lambda: stage_test(a.workers)),
                     ("report", stage_report)):
        if name in a.stages.split(","):
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
