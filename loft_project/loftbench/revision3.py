"""Revision step 3: is federation necessary, or is it attack coverage? (review item 5)

    python -m loftbench.revision3 --out results/revision3 \
        --stages prereg,collect,train,offline,online,report

Every method uses the same detector (17-feature MLP, same epochs), the same
v2.1 policy and the same per-controller calibration rule; only the training
data a controller can use differs:

  local        own benign + own attack exposure
  fedavg       federated over all controllers (v2.1's detector)
  pooled       all controllers' raw data centrally (privacy-violating bound)
  ensemble     average of all controllers' local models (one-shot sharing)
  lib-dms      local + attack runs generated locally from the published DMS-BTT
               settings A1-A3 (a public attack library)
  lib-all      local + every known variant except A6 (best case for libraries)

Experiments: (1) main exposure design, online; (2) leave-one-variant-out over
A1-A7, offline and online on the held-out variant; (3) Dirichlet exposure-skew
sweep, offline. Nothing is tuned; evaluation seeds 7000-7009 are fresh, and
6000+ stays reserved for step 4.
"""
import os

# One BLAS thread per worker process (see experiment.py).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import hashlib
import json
import pickle
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

from .config import DOMAINS, EXPOSURE, VARIANTS, SimConfig
from .data import DOMAIN_IDX, Dataset, collect_run
from .defenses import DualGuard
from .experiment import BUDGET, COLLECT_CFG, EPOCHS, FED_ROUNDS, SPLITS, _dump
from .models import EnsembleModel, threshold_at_fpr, train_federated, train_local
from .revision1 import cluster_boot, cluster_wilcoxon
from .sim import Defense, run_episode
from .traffic import build_traffic

EVAL_SEEDS = list(range(7000, 7010))
LOVO_SEEDS = EVAL_SEEDS[:5]
ALL_V = list(VARIANTS)
KNOWN = [v for v in ALL_V if v != "A6"]
LIB_DMS = ["A1", "A2", "A3"]
METHODS = ["local", "fedavg", "pooled", "ensemble", "lib-dms", "lib-all"]
ALPHAS = [0.05, 0.2, 1.0, 5.0, "inf"]
SWEEP_DRAWS = 3
POLICY = dict(rho=0.7, t_short=1.0, hard=False)    # v2.1, fixed
CFG = SimConfig(duration=300.0)
_CTX = {}


def lovo_exposure(held):
    """Remaining six variants dealt two per controller, round-robin."""
    r = [v for v in ALL_V if v != held]
    return {d: (r[i], r[i + 3]) for i, d in enumerate(DOMAINS)}


HYPOTHESES = dict(
    H1="fedavg harms fewer benign flows than lib-dms (main design, online)",
    H2="fedavg harms fewer benign flows than ensemble (main design, online)",
    H3="fedavg harms fewer benign flows than lib-all (main design, online)",
    H4="fedavg is within 1 percentage point of pooled on benign flows harmed (main design)",
    H5="on held-out variants (LOVO, online) fedavg harms fewer benign flows than local and lib-dms",
    H6="the fedavg - local gap in offline held-out TPR shrinks as exposure skew decreases (alpha up)",
)
DECISION = ("If lib-dms is not worse than fedavg on benign flows harmed (cluster Wilcoxon, "
            "Holm p >= 0.05, or mean difference < 0.5 points), federation is not necessary "
            "given a public attack library: re-scope the paper to the mitigation policy with "
            "federation as an optional deployment. lib-all is reported as an upper bound for "
            "libraries but is not part of the decision, because it assumes generators for "
            "every attack variant are public.")


# ---------------------------------------------------------------- prereg
def stage_prereg(out):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    _dump(out, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), methods=METHODS,
        policy=POLICY, calibration=f"per-domain per-poll, budget {BUDGET}, own validation benign",
        main_exposure=EXPOSURE, lovo_exposure={h: lovo_exposure(h) for h in ALL_V},
        library_dms=LIB_DMS, library_all=KNOWN, alphas=ALPHAS, sweep_draws=SWEEP_DRAWS,
        eval_seeds=EVAL_SEEDS, lovo_online_seeds=LOVO_SEEDS, train_seeds=list(SPLITS["train"]),
        offline_eval="test_off split (seeds 3000-3004)", hypotheses=HYPOTHESES, decision=DECISION,
        reference_baseline="DMS-BTT tuned + blocklist (results/revision2, family B)",
        primary_metric="benign_flows_harmed_frac", statistics="cluster bootstrap / cluster Wilcoxon, Holm"))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


# ---------------------------------------------------------------- collect
def _collect(args):
    d, v, s = args
    return d, v, s, collect_run(d, v, s, COLLECT_CFG)


def stage_collect(out, workers):
    tasks = [(d, v, s) for d in DOMAINS for v in ALL_V + [None] for s in SPLITS["train"]]
    runs = {}
    with get_context("fork").Pool(workers) as p:
        for d, v, s, ds in p.imap_unordered(_collect, tasks):
            runs[(d, v, s)] = ds
    with open(os.path.join(out, "train_runs.pkl"), "wb") as f:
        pickle.dump(runs, f)
    # Identity check: the main-design local training set equals v2's train split.
    src = pickle.load(open(os.path.join(_CTX["src"], "datasets.pkl"), "rb"))
    ok = {}
    for d in DOMAINS:
        mine = assemble(runs, d, EXPOSURE[d])
        ref = src[("train", d)]
        ok[d] = bool(len(mine.y) == len(ref.y) and np.allclose(np.sort(mine.X[:, 0]), np.sort(ref.X[:, 0])))
    _dump(out, "collect_check.json", dict(runs=len(runs), main_train_matches_v2=ok))
    print("collected", len(runs), "runs; matches v2 train split:", ok)


def assemble(runs, d, variants):
    parts = [runs[(d, None, s)] for s in SPLITS["train"]]
    parts += [runs[(d, v, s)] for v in variants for s in SPLITS["train"]]
    return Dataset.concat(parts)


# ---------------------------------------------------------------- train
def _fit_scenario(exposure, runs, library_dms, library_all, seed=0):
    """Train every method for one exposure assignment {domain: variants}."""
    loc = {d: assemble(runs, d, exposure[d]) for d in DOMAINS}
    m = {}
    for d in DOMAINS:
        m[f"local/{d}"] = train_local(loc[d].X, loc[d].y, epochs=EPOCHS, seed=seed)
        for tag, lib in (("lib-dms", library_dms), ("lib-all", library_all)):
            extra = [v for v in lib if v not in exposure[d]]
            ds = assemble(runs, d, list(exposure[d]) + extra)
            m[f"{tag}/{d}"] = train_local(ds.X, ds.y, epochs=EPOCHS, seed=seed)
    ens = EnsembleModel([m[f"local/{d}"] for d in DOMAINS])
    fed, comm, _ = train_federated([(loc[d].X, loc[d].y) for d in DOMAINS], rounds=FED_ROUNDS,
                                   mu=0.0, seed=seed)
    allX = np.concatenate([loc[d].X for d in DOMAINS])
    ally = np.concatenate([loc[d].y for d in DOMAINS])
    pooled = train_local(allX, ally, epochs=EPOCHS, seed=seed)
    for d in DOMAINS:
        m[f"fedavg/{d}"], m[f"pooled/{d}"], m[f"ensemble/{d}"] = fed, pooled, ens
    return m, comm


def _calibrate(m, val):
    return {k: threshold_at_fpr(model.predict_proba(val[k.split("/")[1]].X[val[k.split("/")[1]].y == 0]),
                                BUDGET) for k, model in m.items()}


def _train_task(args):
    kind, key = args
    runs, val = _CTX["runs"], _CTX["val"]
    if kind == "main":
        exp = {d: tuple(EXPOSURE[d]) for d in DOMAINS}
        lib_dms, lib_all = LIB_DMS, KNOWN
    elif kind == "lovo":
        exp = lovo_exposure(key)
        lib_dms = [v for v in LIB_DMS if v != key]
        lib_all = [v for v in ALL_V if v != key]
    else:
        return _sweep_task(key)
    m, comm = _fit_scenario(exp, runs, lib_dms, lib_all)
    return kind, key, m, _calibrate(m, val), dict(exposure=exp, comm=comm)


def _sweep_task(key):
    """Dirichlet exposure: each controller's attack rows are a w-weighted mix of
    the six known variants with a fixed total; benign rows fixed per domain."""
    alpha, draw = key
    runs, val = _CTX["runs"], _CTX["val"]
    r = np.random.default_rng(1000 * draw + (0 if alpha == "inf" else int(100 * alpha)))
    loc, weights = {}, {}
    for d in DOMAINS:
        w = np.full(len(KNOWN), 1 / len(KNOWN)) if alpha == "inf" else r.dirichlet([alpha] * len(KNOWN))
        weights[d] = dict(zip(KNOWN, w.round(4).tolist()))
        ben = Dataset.concat([runs[(d, None, s)] for s in SPLITS["train"]])
        ben_X = [ben.X[ben.y == 0]]
        att_X = []
        n_att = int(sum(assemble(runs, d, EXPOSURE[d]).y))
        for v, wv in zip(KNOWN, w):
            ds = Dataset.concat([runs[(d, v, s)] for s in SPLITS["train"]])
            ben_X.append(ds.X[ds.y == 0])
            a = ds.X[ds.y == 1]
            k = int(round(wv * n_att))
            if k:
                att_X.append(a[r.choice(len(a), min(k, len(a)), replace=k > len(a))])
        Xb, Xa = np.concatenate(ben_X), np.concatenate(att_X)
        loc[d] = (np.concatenate([Xb, Xa]), np.concatenate([np.zeros(len(Xb), np.int8), np.ones(len(Xa), np.int8)]))
    m = {}
    for d in DOMAINS:
        m[f"local/{d}"] = train_local(*loc[d], epochs=EPOCHS)
    ens = EnsembleModel([m[f"local/{d}"] for d in DOMAINS])
    fed, _, _ = train_federated([loc[d] for d in DOMAINS], rounds=FED_ROUNDS, mu=0.0)
    for d in DOMAINS:
        m[f"fedavg/{d}"], m[f"ensemble/{d}"] = fed, ens
    return "sweep", key, m, _calibrate(m, val), dict(weights=weights)


def stage_train(out, workers):
    _CTX["runs"] = pickle.load(open(os.path.join(out, "train_runs.pkl"), "rb"))
    src = pickle.load(open(os.path.join(_CTX["src"], "datasets.pkl"), "rb"))
    _CTX["val"] = {d: src[("val", d)] for d in DOMAINS}
    tasks = [("main", None)] + [("lovo", h) for h in ALL_V] + \
            [("sweep", (a, k)) for a in ALPHAS for k in range(SWEEP_DRAWS)]
    res = {}
    t0 = time.time()
    with get_context("fork").Pool(workers) as p:
        for kind, key, m, taus, info in p.imap_unordered(_train_task, tasks):
            res[(kind, key)] = (m, taus, info)
            print(f"  [train] {kind} {key} done, {time.time() - t0:.0f}s", flush=True)
    with open(os.path.join(out, "models.pkl"), "wb") as f:
        pickle.dump(res, f)
    _dump(out, "train_info.json", {f"{k[0]}:{k[1]}": v[2] for k, v in res.items()})


# ---------------------------------------------------------------- offline
def _tpr_rows(m, taus, test, methods, variants, tag):
    rows = []
    for d in DOMAINS:
        D = test[d]
        vrun = {x["run_id"]: x["variant"] for x in D.runs}
        var = np.array([vrun[r] for r in D.run], dtype=object)
        ben = np.array([x is None for x in var]) & (D.y == 0)
        for meth in methods:
            key = f"{meth}/{d}"
            if key not in m:
                continue
            p = m[key].predict_proba(D.X)
            tau = taus[key]
            for v in variants:
                a = (var == v) & (D.y == 1)
                rows.append(dict(scenario=tag, method=meth, domain=d, variant=v,
                                 tpr=float((p[a] >= tau).mean()), fpr=float((p[ben] >= tau).mean())))
    return rows


def stage_offline(out):
    res = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    src = pickle.load(open(os.path.join(_CTX["src"], "datasets.pkl"), "rb"))
    test = {d: src[("test_off", d)] for d in DOMAINS}
    rows = []
    m, taus, _ = res[("main", None)]
    rows += _tpr_rows(m, taus, test, METHODS, ALL_V, "main")
    for h in ALL_V:
        m, taus, _ = res[("lovo", h)]
        rows += _tpr_rows(m, taus, test, METHODS, [h], f"lovo:{h}")
    for a in ALPHAS:
        for k in range(SWEEP_DRAWS):
            m, taus, info = res[("sweep", (a, k))]
            r = _tpr_rows(m, taus, test, ["local", "fedavg", "ensemble"], ALL_V, f"sweep:{a}:{k}")
            for x in r:
                x["alpha"], x["draw"] = str(a), k
                x["exposure_w"] = info["weights"][x["domain"]].get(x["variant"], 0.0)
            rows += r
    pd.DataFrame(rows).to_csv(os.path.join(out, "offline_tpr.csv"), index=False)


# ---------------------------------------------------------------- online
def _make(name, d, scen):
    if name == "none":
        return Defense()
    if name == "dms-blocklist":
        from . import revision2
        return revision2.make(_CTX["dmsB"], d)
    m, taus, _ = _CTX["res"][scen]
    return DualGuard(m[f"{name}/{d}"], taus[f"{name}/{d}"], **POLICY)


def _episode(args):
    name, scen, d, v, s = args
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       CFG.duration, CFG.attack_start)
    r = run_episode(tr, CFG, _make(name, d, scen), record_ts=False).summary
    return dict(defense=name, scenario=f"{scen[0]}:{scen[1]}", domain=d, variant=v or "benign",
                seed=s, **r)


def stage_online(out, workers):
    from . import revision2
    _CTX["res"] = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    revision2._load(_CTX["rev2"])
    _CTX["dmsB"] = json.load(open(os.path.join(_CTX["rev2"], "selected.json")))["selected"]["B"]
    main = ("main", None)
    tasks = [(n, main, d, v, s) for n in ["none", "dms-blocklist"] + METHODS for d in DOMAINS
             for v in ALL_V + [None] for s in EVAL_SEEDS]
    tasks += [(n, ("lovo", h), d, h, s) for h in ALL_V for n in METHODS for d in DOMAINS
              for s in LOVO_SEEDS]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 300 == 0:
                print(f"  [online] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "online_episodes.csv"), index=False)


# ---------------------------------------------------------------- report
LABEL = {"none": "No defense", "dms-blocklist": "DMS-BTT tuned + blocklist", "local": "Local only",
         "fedavg": "FedAvg (v2.1)", "pooled": "Pooled raw data (oracle)",
         "ensemble": "Ensemble of local models", "lib-dms": "Local + public library (A1-A3)",
         "lib-all": "Local + library of all known variants"}


def stage_report(out):
    from .report import holm
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    df = pd.read_csv(os.path.join(out, "online_episodes.csv"))
    mainx = df[df.scenario == "main:None"]
    att = mainx[mainx.variant != "benign"]
    ben = mainx[mainx.variant == "benign"]
    order = ["none", "dms-blocklist"] + METHODS
    rows = []
    for n in order:
        g, b = att[att.defense == n], ben[ben.defense == n]
        o = g.overflow_seconds_post_attack
        row = {"method": LABEL[n]}
        for mtr, lab in (("benign_flows_harmed_frac", "harmed (%)"), ("avg_attack_occ_post", "mal_occ (%)")):
            mu, lo, hi = cluster_boot(g, mtr)
            row[lab] = f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]"
        row.update(overflow_mean=round(o.mean(), 2), overflow_p90=round(o.quantile(0.9), 2),
                   share_gt_5s=round((o > 5).mean(), 3),
                   benign_only_harmed_pct=round(100 * b.benign_flows_harmed_frac.mean(), 3))
        rows.append(row)
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_main_online.csv"), index=False)
    (att.pivot_table(index="defense", columns="variant", values="benign_flows_harmed_frac") * 100) \
        .round(2).loc[order].rename(index=LABEL).to_csv(os.path.join(tdir, "table_main_by_variant.csv"))
    tests = []
    for mtr in ("benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"):
        for b in order:
            if b == "fedavg":
                continue
            md, w, l, p = cluster_wilcoxon(att, mtr, "fedavg", b)
            tests.append(dict(metric=mtr, baseline=LABEL[b], mean_cluster_diff=md,
                              fedavg_wins=w, fedavg_losses=l, p=p))
    t = pd.DataFrame(tests)
    t["p_holm"] = np.concatenate([holm(g.p.values) for _, g in t.groupby("metric", sort=False)])
    t.to_csv(os.path.join(tdir, "cluster_paired_tests_main.csv"), index=False)

    # Decision rule (pre-registered).
    r = t[(t.metric == "benign_flows_harmed_frac") & (t.baseline == LABEL["lib-dms"])].iloc[0]
    necessary = bool(r.p_holm < 0.05 and -r.mean_cluster_diff >= 0.005)
    _dump(out, "decision.json", dict(rule=DECISION, fedavg_minus_libdms_points=100 * r.mean_cluster_diff,
                                     p_holm=r.p_holm, federation_necessary=necessary))

    # LOVO online: harmed on the held-out variant.
    lv = df[df.scenario.str.startswith("lovo:")]
    lrows = []
    for h in ALL_V:
        g = lv[lv.variant == h]
        row = {"held_out": h}
        for n in METHODS:
            row[LABEL[n]] = round(100 * g[g.defense == n].benign_flows_harmed_frac.mean(), 2)
        lrows.append(row)
    lt = pd.DataFrame(lrows)
    mean_row = {"held_out": "mean"}
    for n in METHODS:
        mu, lo, hi = cluster_boot(lv[lv.defense == n], "benign_flows_harmed_frac")
        mean_row[LABEL[n]] = f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]"
    pd.concat([lt, pd.DataFrame([mean_row])]).to_csv(os.path.join(tdir, "table_lovo_online_harmed.csv"), index=False)
    lo_tests = []
    for b in ("local", "lib-dms", "ensemble", "lib-all", "pooled"):
        m = lv.groupby(["defense", "variant", "domain", "seed"]).benign_flows_harmed_frac.mean().unstack(0)
        from scipy.stats import wilcoxon
        dd = m["fedavg"] - m[b]
        lo_tests.append(dict(baseline=LABEL[b], pairs=len(dd), mean_diff_points=100 * dd.mean(),
                             fedavg_wins=int((dd < 0).sum()), fedavg_losses=int((dd > 0).sum()),
                             p=float(wilcoxon(m["fedavg"], m[b], zero_method="zsplit").pvalue)))
    lt2 = pd.DataFrame(lo_tests)
    lt2["p_holm"] = holm(lt2.p.values)
    lt2.to_csv(os.path.join(tdir, "lovo_online_tests.csv"), index=False)

    # Offline: LOVO TPR and the skew sweep.
    off = pd.read_csv(os.path.join(out, "offline_tpr.csv"))
    lo = off[off.scenario.str.startswith("lovo:")]
    lo.pivot_table(index="variant", columns="method", values="tpr").round(3)[METHODS] \
        .to_csv(os.path.join(tdir, "table_lovo_offline_tpr.csv"))
    sw = off[off.scenario.str.startswith("sweep:")]
    s1 = sw.groupby(["alpha", "method"]).agg(mean_tpr=("tpr", "mean"), mean_fpr=("fpr", "mean")).unstack()
    low = sw[sw.exposure_w < 0.05].groupby(["alpha", "method"]).tpr.mean().unstack()
    s1.columns = [f"{a}_{b}" for a, b in s1.columns]
    s1 = s1.join(low.add_prefix("tpr_low_exposure_"))
    gap = sw.pivot_table(index=["alpha", "draw", "domain", "variant"], columns="method", values="tpr")
    gap = (gap["fedavg"] - gap["local"]).groupby("alpha").agg(["mean", "std"])
    s1 = s1.join(gap.add_prefix("fed_minus_local_tpr_"))
    s1.round(4).to_csv(os.path.join(tdir, "table_skew_sweep_offline.csv"))

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in sorted(os.listdir(tdir)):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))
    print(json.load(open(os.path.join(out, "decision.json"))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--rev2", default="results/revision2")
    ap.add_argument("--out", default="results/revision3")
    ap.add_argument("--stages", default="prereg,collect,train,offline,online,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    _CTX.update(src=a.src, rev2=a.rev2)
    st = a.stages.split(",")
    if "prereg" in st:
        stage_prereg(a.out)
    if "collect" in st:
        stage_collect(a.out, a.workers)
    if "train" in st:
        stage_train(a.out, a.workers)
    if "offline" in st:
        stage_offline(a.out)
    if "online" in st:
        stage_online(a.out, a.workers)
    if "report" in st:
        stage_report(a.out)


if __name__ == "__main__":
    main()
