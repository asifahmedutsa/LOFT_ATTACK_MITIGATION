"""Revision step 2: a fair DMS-BTT comparison (review item 4).

    python -m loftbench.revision2 --out results/revision2 --stages prereg,train,select,test,report

DMS-BTT gets the same selection protocol as v2.1: candidates and rule are
pre-registered, every family is selected on validation seeds 2000-2002 with
v2.1's rule, and the winners are tested once on seeds 5000-5009, which no
DMS-BTT configuration has been tuned on. Seeds 6000+ stay unused.

Families:
  A  DMS-BTT tuned            thresholds H2/H1, flow threshold, Numb = bytes|packets
  B  DMS-BTT + blocklist      A's knobs + refuse re-admission of deleted flows for T s
  C  DMS-BTT detector + DualGuard policy (soft demotion), optional state gate
  D  DMS-BTT federated        FedAvg MLP over (Numb, PIT, Sizep), two-level policy
  E  DMS features federated + v2.1 policy   (isolates our features from federation)
"""
import os

# One BLAS thread per worker process (see experiment.py).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import itertools
import json
import pickle
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

from . import v21
from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DMSBTT, DualGuard, dms_transform
from .experiment import BUDGET, FED_ROUNDS, SPLITS, _dump
from .models import CatWrap, DMSFeatureMLP, threshold_at_fpr, train_federated
from .revision1 import cluster_boot, cluster_wilcoxon
from .sim import run_episode
from .traffic import build_traffic

TEST_SEEDS = v21.FRESH_SEEDS
CFG = SimConfig(duration=300.0)


def candidates():
    c = []
    for h2, h1, p, nb in itertools.product([0.6, 0.7, 0.75, 0.8], [0.85, 0.95], [0.3, 0.5, 0.7],
                                           ["bytes", "packets"]):
        c.append(dict(family="A", h2=h2, h1=h1, p=p, numb=nb))
    for h2, p, T, nb in itertools.product([0.6, 0.75], [0.5, 0.7], [10, 30, 60], ["bytes", "packets"]):
        c.append(dict(family="B", h2=h2, h1=0.9, p=p, numb=nb, block=T))
    for rho, gate, hard, nb in itertools.product([0.5, 0.7], [True, False], ["off", "h0.90"],
                                                 ["bytes", "packets"]):
        c.append(dict(family="C", rho=rho, gate=gate, hard=hard, numb=nb))
    for h2, p in itertools.product([0.6, 0.75], [0.3, 0.5, 0.7]):
        c.append(dict(family="D", h2=h2, h1=0.9, p=p, numb="bytes"))
    for rho in (0.5, 0.7):
        c.append(dict(family="E", rho=rho, numb="bytes"))
    for x in c:
        x["id"] = ",".join(f"{k}={v}" for k, v in x.items())
    return c


RULE = dict(v21.RULE, fallback=(
    "if no candidate in a family is feasible, minimize the summed relative constraint "
    "violation, then the objective (v2.1 never reached its fallback, so this does not "
    "change v2.1's selection)"))
_CTX = {}


# ---------------------------------------------------------------- prereg
def stage_prereg(out):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    cands = candidates()
    _dump(out, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        purpose="Fair DMS-BTT comparison: same validation selection budget/rule as v2.1",
        n_candidates=len(cands), families={f: sum(c["family"] == f for c in cands) for f in "ABCDE"},
        v21_candidates_for_reference=24, candidates=cands, rule=RULE,
        selection="per family, validation seeds only", validation_seeds=list(SPLITS["val"]),
        test_seeds=TEST_SEEDS, test_reuse_note="Seeds 5000-5009 were used to test v2.1 but never "
        "to tune any DMS-BTT configuration; v2.1 rows are reused from results/revision1.",
        calibration_budget=BUDGET,
        numb_note="Both Numb definitions are tuned; report the one matching the DMS-BTT paper "
                  "(Section 4) as primary once checked."))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", len(cands), "candidates", h[:16])


# ---------------------------------------------------------------- train
def stage_train(src, out):
    from catboost import CatBoostClassifier
    data = pickle.load(open(os.path.join(src, "datasets.pkl"), "rb"))
    models, _ = pickle.load(open(os.path.join(src, "models.pkl"), "rb"))
    m, taus = {}, {}
    for d in DOMAINS:
        tr, va = data[("train", d)], data[("val", d)]
        m[f"state/{d}"] = models[f"dms_state/{d}"]
        m[f"flow/bytes/{d}"] = models[f"dms_flow/{d}"]
        fm = CatBoostClassifier(loss_function="Logloss", iterations=300, random_seed=0,
                                verbose=False, thread_count=4)
        fm.fit(dms_transform(tr.dms, "packets"), tr.y)
        m[f"flow/packets/{d}"] = CatWrap(fm)
    fed, comm, _ = train_federated(
        [(DMSFeatureMLP.features(data[("train", d)].dms), data[("train", d)].y) for d in DOMAINS],
        rounds=FED_ROUNDS, mu=0.0)
    m["fed_dms"] = DMSFeatureMLP(fed)
    for d in DOMAINS:
        va = data[("val", d)]
        ben = va.dms[va.y == 0]
        for nb in ("bytes", "packets"):
            p = m[f"flow/{nb}/{d}"].predict_proba(dms_transform(ben, nb))[:, 1]
            taus[f"flow/{nb}/{d}"] = threshold_at_fpr(p, BUDGET)
        taus[f"fed_dms/{d}"] = threshold_at_fpr(m["fed_dms"].predict_proba(ben), BUDGET)
    with open(os.path.join(out, "models.pkl"), "wb") as f:
        pickle.dump((m, taus), f)
    _dump(out, "train_info.json", dict(fed_dms_comm=comm, taus=taus))


# ---------------------------------------------------------------- episodes
def make(c, d):
    m, taus = _CTX["m"], _CTX["taus"]
    fam, nb = c["family"], c.get("numb", "bytes")
    if fam in ("A", "B"):
        return DMSBTT(m[f"state/{d}"], m[f"flow/{nb}/{d}"], h1=c["h1"], h2=c["h2"],
                      p_thresh=c["p"], numb_mode=nb, blocklist_s=c.get("block", 0.0))
    if fam == "D":
        return DMSBTT(m[f"state/{d}"], m["fed_dms"], h1=c["h1"], h2=c["h2"], p_thresh=c["p"])
    if fam == "C":
        return DualGuard(m[f"flow/{nb}/{d}"], taus[f"flow/{nb}/{d}"], rho=c["rho"], t_short=1.0,
                         hard=c["hard"] != "off", h_crit=0.90, inputs="dms", numb_mode=nb,
                         state_model=m[f"state/{d}"] if c["gate"] else None)
    if fam == "E":
        return DualGuard(m["fed_dms"], taus[f"fed_dms/{d}"], rho=c["rho"], t_short=1.0,
                         hard=False, inputs="dms")
    raise ValueError(fam)


def _episode(args):
    c, d, v, s = args
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       CFG.duration, CFG.attack_start)
    r = run_episode(tr, CFG, make(c, d), record_ts=False).summary
    return dict(cfg_id=c["id"], family=c["family"], domain=d, variant=v or "benign", seed=s, **r)


def _run(tasks, workers, tag):
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 300 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


def _load(out):
    m, taus = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    _CTX.update(m=m, taus=taus)


# ---------------------------------------------------------------- select
def select_family(g):
    c = RULE["constraints"]
    viol = (np.maximum(0, g.avg_attack_occ_post / c["avg_attack_occ_post_max"] - 1)
            + np.maximum(0, g.overflow_seconds_post_attack / c["overflow_seconds_post_attack_max"] - 1)
            + np.maximum(0, g.benign_only_impacted / c["benign_only_impacted_max"] - 1))
    g = g.assign(violation=viol, feasible=viol == 0)
    best = g.sort_values(["violation", "benign_flows_impacted_frac"]).iloc[0]
    return g, best


def stage_select(out, workers):
    if not os.path.exists(os.path.join(out, "preregistration.json")):
        raise SystemExit("run the prereg stage first")
    _load(out)
    cands = json.load(open(os.path.join(out, "preregistration.json")))["candidates"]
    tasks = [(c, d, v, s) for c in cands for d in DOMAINS for v in list(VARIANTS) + [None]
             for s in SPLITS["val"]]
    df = _run(tasks, workers, "select")
    df.to_csv(os.path.join(out, "selection_validation.csv"), index=False)
    att = df[df.variant != "benign"].groupby(["family", "cfg_id"])[
        ["benign_flows_impacted_frac", "benign_flows_harmed_frac", "avg_attack_occ_post",
         "overflow_seconds_post_attack"]].mean()
    ben = df[df.variant == "benign"].groupby(["family", "cfg_id"]).benign_flows_impacted_frac.mean()
    tab = att.join(ben.rename("benign_only_impacted")).reset_index()
    rows, selected = [], {}
    for fam, g in tab.groupby("family"):
        g, best = select_family(g)
        rows.append(g)
        selected[fam] = next(c for c in cands if c["id"] == best.cfg_id)
        print(f"family {fam}: {best.cfg_id}  feasible={bool(best.feasible)} "
              f"impacted={best.benign_flows_impacted_frac:.4f} occ={best.avg_attack_occ_post:.4f} "
              f"ovf={best.overflow_seconds_post_attack:.2f}")
    pd.concat(rows).to_csv(os.path.join(out, "selection_table.csv"), index=False)
    _dump(out, "selected.json", dict(selected=selected))


# ---------------------------------------------------------------- test
def stage_test(out, workers):
    path = os.path.join(out, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run; refusing to rerun (one-shot evaluation)")
    _load(out)
    sel = json.load(open(os.path.join(out, "selected.json")))["selected"]
    tasks = [(c, d, v, s) for c in sel.values() for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in TEST_SEEDS]
    _run(tasks, workers, "test").to_csv(path, index=False)


# ---------------------------------------------------------------- report
NAMES = {"A": "DMS-BTT tuned", "B": "DMS-BTT tuned + blocklist",
         "C": "DMS-BTT detector + DualGuard policy", "D": "DMS-BTT federated (MLP)",
         "E": "Federated DMS features + v2.1 policy"}


def stage_report(out, rev1):
    t = pd.read_csv(os.path.join(out, "test_episodes.csv"))
    t["defense"] = t.family.map(lambda f: f"dms-{f}")
    r1 = pd.read_csv(os.path.join(rev1, "remeasure_episodes.csv"))
    r1 = r1[r1.defense.isin(["none", "dms-btt", "dg-local-noctx", "v2.1"])]
    df = pd.concat([r1, t], ignore_index=True)
    label = {"none": "No defense", "dms-btt": "DMS-BTT (original knobs)",
             "dg-local-noctx": "Local MLP (no ctx) + v2.1 policy", "v2.1": "FL-DualGuard v2.1",
             **{f"dms-{f}": n for f, n in NAMES.items()}}
    order = ["none", "dms-btt", "dms-A", "dms-B", "dms-C", "dms-D", "dms-E", "dg-local-noctx", "v2.1"]
    att = df[df.variant != "benign"]
    ben = df[df.variant == "benign"]
    sel = json.load(open(os.path.join(out, "selected.json")))["selected"]
    rows = []
    for d in order:
        g, b = att[att.defense == d], ben[ben.defense == d]
        o = g.overflow_seconds_post_attack
        f = d.split("-")[1] if d.startswith("dms-") and d != "dms-btt" else None
        row = {"defense": label[d], "config": sel[f]["id"] if f else ""}
        for m, lab in (("benign_flows_harmed_frac", "harmed"), ("benign_flows_impacted_frac", "impacted"),
                       ("avg_attack_occ_post", "mal_occ")):
            mu, lo, hi = cluster_boot(g, m)
            row[f"{lab} (%)"] = f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]"
        row.update(overflow_mean=round(o.mean(), 2), overflow_p90=round(o.quantile(0.9), 2),
                   share_gt_5s=round((o > 5).mean(), 3),
                   benign_only_harmed_pct=round(100 * b.benign_flows_harmed_frac.mean(), 3),
                   blocked_benign_pct=round(100 * g.get("benign_flows_blocked_frac", pd.Series([0])).fillna(0).mean(), 3))
        rows.append(row)
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_dms_fair.csv"), index=False)
    tests = []
    for m in ("benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"):
        for b in order:
            if b == "v2.1":
                continue
            md, w, l, p = cluster_wilcoxon(att, m, "v2.1", b)
            tests.append(dict(metric=m, baseline=label[b], mean_cluster_diff=md,
                              v21_cluster_wins=w, v21_cluster_losses=l, p=p))
    from .report import holm
    tt = pd.DataFrame(tests)
    tt["p_holm"] = np.concatenate([holm(g.p.values) for _, g in tt.groupby("metric", sort=False)])
    tt.to_csv(os.path.join(tdir, "cluster_paired_tests.csv"), index=False)
    pv = (att.pivot_table(index="defense", columns="variant", values="benign_flows_harmed_frac") * 100).round(2)
    pv.loc[[o for o in order if o in pv.index]].rename(index=label).to_csv(
        os.path.join(tdir, "table_harmed_by_variant.csv"))
    # Numb sensitivity on validation: best feasible-or-least-violating per family and Numb.
    st = pd.read_csv(os.path.join(out, "selection_table.csv"))
    st["numb"] = st.cfg_id.str.extract(r"numb=(\w+)")
    sens = []
    for (fam, nb), g in st[st.family.isin(["A", "B", "C"])].groupby(["family", "numb"]):
        _, best = select_family(g.drop(columns=["violation", "feasible"]))
        sens.append(dict(family=NAMES[fam], numb=nb, cfg=best.cfg_id, feasible=bool(best.feasible),
                         val_impacted=round(100 * best.benign_flows_impacted_frac, 2),
                         val_harmed=round(100 * best.benign_flows_harmed_frac, 2),
                         val_mal_occ=round(100 * best.avg_attack_occ_post, 2),
                         val_overflow=round(best.overflow_seconds_post_attack, 2)))
    pd.DataFrame(sens).to_csv(os.path.join(tdir, "table_numb_sensitivity_validation.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 60)
    for f in sorted(os.listdir(tdir)):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--rev1", default="results/revision1")
    ap.add_argument("--out", default="results/revision2")
    ap.add_argument("--stages", default="prereg,train,select,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    st = a.stages.split(",")
    if "prereg" in st:
        stage_prereg(a.out)
    if "train" in st:
        stage_train(a.src, a.out)
    if "select" in st:
        stage_select(a.out, a.workers)
    if "test" in st:
        stage_test(a.out, a.workers)
    if "report" in st:
        stage_report(a.out, a.rev1)


if __name__ == "__main__":
    main()
