"""E2 (docs/other_papers_run_plan.md): FTMaster, FTOP, FloRa and rDefender against
FL-DualGuard on the same simulator, traffic and seeds.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.e2_baselines --stages collect,train,select,test,report

Stages:
  collect  table-level training data for the FTMaster and FTOP detectors: every poll of
           each controller's training runs (its exposure attacks + benign, seeds 1000-1004),
           labelled 1 while an attack is active
  train    per-controller classifiers, as for DMS-BTT: FTMaster XGBoost (table + rule),
           FTOP Random Forest (table + rule), FloRa CatBoost (rule); rule classifiers use
           the saved v2 training rows
  select   validation seeds 2000-2002, D1-D3, A1-A7 + benign: knobs the papers do not state
           (FloRa trigger and block limit, rDefender gamma) chosen by v2.1's own rule; also
           gate G1 (each baseline lowers the attacker's table share against no defense)
  test     seeds 11000-11009 (unused), 300 s, dedicated ports, one shot
  report   tables in DMS-BTT's format plus benign harm and paired tests against v2.1

Writes results/e2_baselines/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import itertools
import json
import pickle
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import revision1 as R1
from . import v21
from .baselines import (FloRa, FTMaster, FTOP, RDefender, flora_rule_features,
                        ftmaster_rule_features, ftmaster_table_features, ftop_rule_features,
                        ftop_table_features)
from .config import DOMAINS, EXPOSURE, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import OVSEvict, PortGuard
from .experiment import COLLECT_CFG, SPLITS, _dump
from .ports import assign_ports
from .sim import run_episode
from .traffic import build_traffic

OUT = "results/e2_baselines"
TEST_SEEDS = list(range(11000, 11010))
TEST_DEFENSES = ["none", "ovs-evict", "dms-btt", "ftmaster", "ftop", "flora", "rdefender",
                 "v2.1", "v2.1+portguard"]
KNOBS = {"flora": dict(trigger=[0.5, 0.7, 0.9], block_after=[10, 50, 1750]),
         "rdefender": dict(gamma=[0.02, 0.05, 0.1]),
         "ftmaster": {}, "ftop": {}}
LABEL = {"none": "No defense (REFUSE)", "ovs-evict": "EVICT (OVS)", "dms-btt": "DMS-BTT",
         "ftmaster": "FTMaster", "ftop": "FTOP", "flora": "FloRa", "rdefender": "rDefender",
         "v2.1": "FL-DualGuard v2.1", "v2.1+portguard": "FL-DualGuard v2.1 + PortGuard"}
_M = {}


class _OneThread:
    """Serve a fitted classifier on one core inside a pool worker."""

    def __init__(self, m):
        self.m = m
        if hasattr(m, "n_jobs"):
            m.n_jobs = 1
        if type(m).__module__.startswith("xgboost"):
            m.set_params(n_jobs=1)

    def _kw(self):
        return {"thread_count": 1} if type(self.m).__module__.startswith("catboost") else {}

    def predict(self, Z):
        return self.m.predict(Z, **self._kw())

    def predict_proba(self, Z):
        return self.m.predict_proba(Z, **self._kw())


# ------------------------------------------------------------------ collect
def _collect_task(args):
    d, v, s = args
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       COLLECT_CFG.duration, COLLECT_CFG.attack_start)
    rows = []

    def hook(t, fids, obs, lab):
        on = v is not None and any(a <= t <= b + 1e-9 for a, b in tr.attack_active)
        rows.append(np.r_[ftmaster_table_features(t, obs, tr.flow_src), ftop_table_features(obs),
                          int(on)])

    run_episode(tr, COLLECT_CFG, collect=hook, record_ts=False)
    return d, np.array(rows, np.float32)


def stage_collect(workers):
    tasks = [(d, v, s) for d in DOMAINS for v in list(EXPOSURE[d]) + [None] for s in SPLITS["train"]]
    with get_context("fork").Pool(workers) as p:
        res = p.map(_collect_task, tasks)
    tab = {d: np.concatenate([a for dd, a in res if dd == d]) for d in DOMAINS}
    with open(os.path.join(OUT, "table_data.pkl"), "wb") as f:
        pickle.dump(tab, f)
    print({d: (a.shape, round(float(a[:, -1].mean()), 3)) for d, a in tab.items()})


# ------------------------------------------------------------------ train
def stage_train():
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    tab = pickle.load(open(os.path.join(OUT, "table_data.pkl"), "rb"))
    models, info = {}, {}
    for d in DOMAINS:
        tr = data[("train", d)]
        T = tab[d]
        t0 = time.time()
        models[f"ftmaster_state/{d}"] = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4,
                                                      random_state=0).fit(T[:, :8], T[:, -1])
        models[f"ftmaster_rule/{d}"] = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4,
                                                     random_state=0).fit(ftmaster_rule_features(tr.X), tr.y)
        models[f"ftop_state/{d}"] = RandomForestClassifier(100, n_jobs=4, random_state=0).fit(
            T[:, 8:12], T[:, -1])
        models[f"ftop_rule/{d}"] = RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4,
                                                          random_state=0).fit(ftop_rule_features(tr.X), tr.y)
        models[f"flora_rule/{d}"] = CatBoostClassifier(iterations=300, random_seed=0, verbose=False,
                                                       thread_count=4).fit(flora_rule_features(tr.X), tr.y)
        info[d] = dict(table_rows=int(len(T)), table_attack_frac=float(T[:, -1].mean()),
                       rule_rows=int(len(tr.y)), seconds=round(time.time() - t0, 1))
        print(d, info[d], flush=True)
    with open(os.path.join(OUT, "models.pkl"), "wb") as f:
        pickle.dump(models, f)
    _dump(OUT, "train_info.json", info)


# ------------------------------------------------------------------ episodes
def _load(src="results/v2", v21_dir="results/v21"):
    sel = json.load(open(os.path.join(v21_dir, "selected.json")))["selected"]
    v21._load_ctx(src, v21_dir, sel)
    m = pickle.load(open(os.path.join(OUT, "models.pkl"), "rb"))
    _M["models"] = {k: _OneThread(x) for k, x in m.items()}
    _M["pfs"] = json.load(open("results/revision4b/selected.json"))["selected"]
    p = os.path.join(OUT, "selected.json")
    _M["knobs"] = json.load(open(p))["selected"] if os.path.exists(p) else {}


def _make(name, d, knobs=None):
    m = _M["models"]
    k = knobs if knobs is not None else _M["knobs"].get(name, {})
    if name == "none":
        return v21._make("none", d, None)
    if name == "ovs-evict":
        return OVSEvict()
    if name in ("dms-btt", "v2.1"):
        return v21._make(name, d, None)
    if name == "v2.1+portguard":
        P = _M["pfs"]
        return PortGuard(v21._make("v2.1", d, None), name=name,
                         **{x: P[x] for x in ("mode", "share", "q", "rho_q", "hold_s", "tau_s")})
    if name == "ftmaster":
        return FTMaster(m[f"ftmaster_state/{d}"], m[f"ftmaster_rule/{d}"], **k)
    if name == "ftop":
        return FTOP(m[f"ftop_state/{d}"], m[f"ftop_rule/{d}"], **k)
    if name == "flora":
        return FloRa(m[f"flora_rule/{d}"], **k)
    if name == "rdefender":
        return RDefender(**k)
    raise ValueError(name)


def _episode(args):
    name, knobs, d, v, s = args
    cfg = SimConfig(duration=300.0)
    tr = assign_ports(build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                                    cfg.duration, cfg.attack_start), "dedicated")
    r = run_episode(tr, cfg, _make(name, d, knobs), record_ts=False).summary
    row = dict(defense=name, domain=d, variant=v or "benign", seed=s, **r)
    if knobs:
        row["knobs"] = json.dumps(knobs, sort_keys=True)
    return row


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 100 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ select
def stage_select(workers):
    _load()
    cells = [(d, v, s) for d in DOMAINS for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
    tasks = [("none", None, *c) for c in cells]
    for name, grid in KNOBS.items():
        combos = [dict(zip(grid, c)) for c in itertools.product(*grid.values())] if grid else [{}]
        tasks += [(name, k, *c) for k in combos for c in cells]
    df = _run(tasks, workers, "select")
    df["knobs"] = df.get("knobs", pd.Series(index=df.index, dtype=object)).fillna("{}")
    df.to_csv(os.path.join(OUT, "selection_validation.csv"), index=False)
    c = v21.RULE["constraints"]
    att, ben = df[df.variant != "benign"], df[df.variant == "benign"]
    g = att.groupby(["defense", "knobs"])[["benign_flows_harmed_frac", "avg_attack_occ_post",
                                           "overflow_seconds_post_attack"]].mean()
    g = g.join(ben.groupby(["defense", "knobs"]).benign_flows_harmed_frac.mean()
               .rename("benign_only_harmed")).reset_index()
    g["feasible"] = ((g.avg_attack_occ_post <= c["avg_attack_occ_post_max"])
                     & (g.overflow_seconds_post_attack <= c["overflow_seconds_post_attack_max"])
                     & (g.benign_only_harmed <= c["benign_only_impacted_max"]))
    none_occ = float(g[g.defense == "none"].avg_attack_occ_post.iloc[0])
    sel, gate = {}, {}
    for name in KNOBS:
        h = g[g.defense == name]
        best = (h[h.feasible].sort_values("benign_flows_harmed_frac") if h.feasible.any()
                else h.sort_values("overflow_seconds_post_attack")).iloc[0]
        sel[name] = json.loads(best.knobs)
        gate[name] = dict(feasible=bool(best.feasible), knobs=sel[name],
                          attack_occ=round(float(best.avg_attack_occ_post), 4),
                          attack_occ_none=round(none_occ, 4),
                          passes_G1=bool(best.avg_attack_occ_post < 0.5 * none_occ),
                          harmed=round(float(best.benign_flows_harmed_frac), 4),
                          overflow_s=round(float(best.overflow_seconds_post_attack), 2))
    g.to_csv(os.path.join(OUT, "selection_table.csv"), index=False)
    _dump(OUT, "selected.json", dict(selected=sel, gate=gate, rule=v21.RULE,
                                     note="G1: the selected setting at least halves the attacker's "
                                          "table share against no defense on validation seeds"))
    print(g.round(4).to_string(index=False))
    print(json.dumps(gate, indent=1))


# ------------------------------------------------------------------ test
def stage_test(workers):
    path = os.path.join(OUT, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load()
    tasks = [(n, None, d, v, s) for n in TEST_DEFENSES for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in TEST_SEEDS]
    _run(tasks, workers, "test").to_csv(path, index=False)


# ------------------------------------------------------------------ report
def stage_report():
    df = pd.read_csv(os.path.join(OUT, "test_episodes.csv"))
    tdir = os.path.join(OUT, "tables")
    os.makedirs(tdir, exist_ok=True)
    att = df[df.variant != "benign"]
    rows = []
    for d in TEST_DEFENSES:
        g = att[att.defense == d]
        b = df[(df.defense == d) & (df.variant == "benign")]
        fo = g.first_overflow_s.dropna()
        rows.append({
            "defense": LABEL[d],
            "Avg Pa (%)": round(100 * g.avg_attack_occ_post.mean(), 2),
            "Max Pa (%)": round(100 * g.max_attack_occ.mean(), 2),
            "Avg table usage (%)": round(100 * (g.avg_attack_occ + g.avg_benign_occ).mean(), 2),
            "Earliest overflow (s)": round(fo.mean(), 1) if len(fo) else "never",
            "Runs with overflow (%)": round(100 * g.first_overflow_s.notna().mean(), 1),
            "Overflow after attack (s)": round(g.overflow_seconds_post_attack.mean(), 2),
            "Packet-In": int(g.packet_in.mean()),
            "TABLE_FULL": int(g.table_full.mean()),
            "Benign harmed (%)": R1._fmt(g, "benign_flows_harmed_frac"),
            "Benign harmed, no attack (%)": R1._fmt(b, "benign_flows_harmed_frac"),
            "Benign Packet-In lost (%)": round(100 * (g.benign_rejected_pkts / g.benign_pkts).mean(), 2),
            "Decision time (ms)": round(g.decision_ms_mean.mean(), 2),
        })
    main = pd.DataFrame(rows)
    main.to_csv(os.path.join(tdir, "table_main.csv"), index=False)
    by_var = (att.pivot_table(index="defense", columns="variant", values="benign_flows_harmed_frac")
              * 100).round(2).reindex(TEST_DEFENSES).rename(index=LABEL)
    by_var.to_csv(os.path.join(tdir, "harm_by_variant.csv"))
    occ_var = (att.pivot_table(index="defense", columns="variant", values="avg_attack_occ_post")
               * 100).round(2).reindex(TEST_DEFENSES).rename(index=LABEL)
    occ_var.to_csv(os.path.join(tdir, "attack_share_by_variant.csv"))
    by_dom = (att.pivot_table(index="defense", columns="domain", values="benign_flows_harmed_frac")
              * 100).round(2).reindex(TEST_DEFENSES).rename(index=LABEL)
    by_dom.to_csv(os.path.join(tdir, "harm_by_domain.csv"))
    from .report import holm
    tests = []
    for m in ("benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"):
        for b in TEST_DEFENSES:
            if b == "v2.1":
                continue
            md, w, l, p = R1.cluster_wilcoxon(att, m, "v2.1", b)
            tests.append(dict(metric=m, baseline=LABEL[b], mean_diff_v21_minus=md, v21_lower=w,
                              v21_higher=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = np.concatenate([holm(g.p.values) for _, g in t.groupby("metric", sort=False)])
    t.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    pd.set_option("display.width", 250)
    print(main.to_string(index=False))
    print(by_var.to_string())
    print(occ_var.to_string())
    print(t.round(5).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="collect,train,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    st = a.stages.split(",")
    t0 = time.time()
    for name, fn in (("collect", lambda: stage_collect(a.workers)), ("train", stage_train),
                     ("select", lambda: stage_select(a.workers)),
                     ("test", lambda: stage_test(a.workers)), ("report", stage_report)):
        if name in st:
            print(f"== {name}", flush=True)
            fn()
            print(f"== {name} done, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
