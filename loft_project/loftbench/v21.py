"""v2.1: validation-only configuration selection, then one evaluation on fresh seeds.

    python -m loftbench.v21 --src results/v2 --out results/v21 --stages prereg,train,select,test,report

The candidate set and selection rule are written to preregistration.json
before any validation episode runs (stage "prereg"); "select" refuses to run
without it. The test stage uses seeds 5000-5009, which no earlier stage has
touched, and runs once: it refuses to overwrite existing test results.
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

from .config import DOMAINS, VARIANTS, SimConfig
from .data import DOMAIN_IDX
from .defenses import DMSBTT, DualGuard
from .experiment import BUDGET, EPOCHS, FED_ROUNDS, SPLITS, _dump
from .features import CONTEXT_FEATURES, FEATURE_NAMES
from .models import SubsetModel, threshold_at_fpr, train_federated, train_local
from .sim import Defense, run_episode
from .traffic import build_traffic

FRESH_SEEDS = list(range(5000, 5010))
CANDIDATES = dict(
    detector=["fedprox", "fedavg", "fedprox_noctx", "fedavg_noctx"],
    hard=["h0.90", "h0.95", "off"],
    rho=[0.5, 0.7],
    t_short=[1.0],
)
RULE = dict(
    objective="minimize mean benign_flows_impacted_frac over attacked validation episodes",
    constraints=dict(avg_attack_occ_post_max=0.15, overflow_seconds_post_attack_max=5.0,
                     benign_only_impacted_max=0.01),
    tie_break="prefer hard=off, then *_noctx, then fedavg (simpler)",
    fallback="if no candidate is feasible, minimize overflow_seconds_post_attack",
)
TEST_DEFENSES = ["none", "dms-btt", "dg-local", "dg-local-noctx", "v2", "v2.1", "dg-pooled"]

_CTX = None


def _noctx_idx():
    return [i for i, f in enumerate(FEATURE_NAMES) if f not in CONTEXT_FEATURES]


def stage_prereg(out):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    doc = dict(created_utc=datetime.now(timezone.utc).isoformat(), candidates=CANDIDATES,
               rule=RULE, validation_seeds=list(SPLITS["val"]), fresh_test_seeds=FRESH_SEEDS,
               test_defenses=TEST_DEFENSES, calibration_budget=BUDGET,
               note="Motivated by v2 test-set ablations (results_v2.md section 5); selection "
                    "uses validation seeds only and the test runs once on unseen seeds.")
    _dump(out, "preregistration.json", doc)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


def stage_train(src, out):
    data = pickle.load(open(os.path.join(src, "datasets.pkl"), "rb"))
    models, taus = pickle.load(open(os.path.join(src, "models.pkl"), "rb"))
    idx = _noctx_idx()
    tr = {d: data[("train", d)] for d in DOMAINS}
    clients = [(tr[d].X[:, idx], tr[d].y) for d in DOMAINS]
    m, comm, _ = train_federated(clients, rounds=FED_ROUNDS, mu=0.0)
    models["fedavg_noctx"] = SubsetModel(m, idx)
    for d in DOMAINS:
        models[f"local_noctx/{d}"] = SubsetModel(
            train_local(tr[d].X[:, idx], tr[d].y, epochs=EPOCHS), idx)
    for key in ["fedavg_noctx"]:
        for d in DOMAINS:
            v = data[("val", d)]
            taus[f"{key}/{d}"] = threshold_at_fpr(models[key].predict_proba(v.X[v.y == 0]), BUDGET)
    for d in DOMAINS:
        v = data[("val", d)]
        k = f"local_noctx/{d}"
        taus[k] = threshold_at_fpr(models[k].predict_proba(v.X[v.y == 0]), BUDGET)
    with open(os.path.join(out, "models.pkl"), "wb") as f:
        pickle.dump((models, taus), f)
    _dump(out, "train_info.json", dict(fedavg_noctx_comm=comm))


def _policy(cfg):
    h = cfg["hard"]
    return dict(rho=cfg["rho"], t_short=cfg["t_short"], hard=h != "off",
                h_crit=0.90 if h == "off" else float(h[1:]))


def _make(name, d, extra):
    models, taus, v2knobs, sel = _CTX
    if name == "none":
        return Defense()
    if name == "dms-btt":
        return DMSBTT(models[f"dms_state/{d}"], models[f"dms_flow/{d}"])
    if name == "dg-local":
        return DualGuard(models[f"local/{d}"], taus[f"local/{d}"], **v2knobs)
    if name == "dg-local-noctx":
        return DualGuard(models[f"local_noctx/{d}"], taus[f"local_noctx/{d}"], **_policy(sel))
    if name == "dg-pooled":
        return DualGuard(models["pooled"], taus[f"pooled/{d}"], **v2knobs)
    if name == "v2":
        return DualGuard(models["fedprox"], taus[f"fedprox/{d}"], **v2knobs)
    if name == "v2.1":
        return DualGuard(models[sel["detector"]], taus[f"{sel['detector']}/{d}"], **_policy(sel))
    if name == "cand":
        return DualGuard(models[extra["detector"]], taus[f"{extra['detector']}/{d}"], **_policy(extra))
    raise ValueError(name)


def _episode(args):
    name, extra, d, v, s, keep_ts = args
    cfg = SimConfig(duration=300.0)
    tr = build_traffic(DOMAINS[d], DOMAIN_IDX[d], VARIANTS[v] if v else None, s,
                       cfg.duration, cfg.attack_start)
    r = run_episode(tr, cfg, _make(name, d, extra), record_ts=keep_ts)
    row = dict(defense=name, domain=d, variant=v or "benign", seed=s, **r.summary)
    if extra:
        row.update({f"cfg_{k}": val for k, val in extra.items()})
    return row, (r.timeseries if keep_ts else None)


def _run(tasks, workers, tag):
    rows, series = [], {}
    t0 = time.time()
    with get_context("fork").Pool(workers) as p:
        for i, (row, ts) in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if ts is not None:
                series[(row["defense"], row["domain"], row["variant"])] = ts
            if (i + 1) % 200 == 0:
                print(f"  [{tag}] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows), series


def _load_ctx(src, out, sel=None):
    global _CTX
    models, taus = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    t = json.load(open(os.path.join(src, "tuned_policy.json")))
    _CTX = (models, taus, dict(rho=t["rho"], t_short=t["t_short"]), sel)


def stage_select(src, out, workers):
    if not os.path.exists(os.path.join(out, "preregistration.json")):
        raise SystemExit("run the prereg stage first")
    _load_ctx(src, out)
    cands = [dict(zip(CANDIDATES, c)) for c in itertools.product(*CANDIDATES.values())]
    tasks = [("cand", c, d, v, s, False) for c in cands for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
    df, _ = _run(tasks, workers, "select")
    df.to_csv(os.path.join(out, "selection_validation.csv"), index=False)
    keys = [f"cfg_{k}" for k in CANDIDATES]
    att = df[df.variant != "benign"].groupby(keys)[
        ["benign_flows_impacted_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"]].mean()
    ben = df[df.variant == "benign"].groupby(keys).benign_flows_impacted_frac.mean()
    g = att.join(ben.rename("benign_only_impacted")).reset_index()
    c = RULE["constraints"]
    g["feasible"] = ((g.avg_attack_occ_post <= c["avg_attack_occ_post_max"])
                     & (g.overflow_seconds_post_attack <= c["overflow_seconds_post_attack_max"])
                     & (g.benign_only_impacted <= c["benign_only_impacted_max"]))
    g["tb"] = list(zip(g.cfg_hard != "off", ~g.cfg_detector.str.endswith("noctx"),
                       ~g.cfg_detector.str.startswith("fedavg")))
    if g.feasible.any():
        best = g[g.feasible].sort_values(["benign_flows_impacted_frac", "tb"]).iloc[0]
    else:
        best = g.sort_values("overflow_seconds_post_attack").iloc[0]
    sel = {k: best[f"cfg_{k}"] for k in CANDIDATES}
    sel = {k: (float(v) if isinstance(v, (np.floating, float)) else str(v)) for k, v in sel.items()}
    g.drop(columns="tb").to_csv(os.path.join(out, "selection_table.csv"), index=False)
    _dump(out, "selected.json", dict(selected=sel, feasible_count=int(g.feasible.sum()),
                                     validation_metrics=best.drop(labels="tb").to_dict()))
    print(g.drop(columns="tb").round(4).to_string(index=False))
    print("SELECTED", sel)


def stage_test(src, out, workers):
    path = os.path.join(out, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("fresh-seed test already run; refusing to rerun (one-shot evaluation)")
    sel = json.load(open(os.path.join(out, "selected.json")))["selected"]
    _load_ctx(src, out, sel)
    tasks = [(n, None, d, v, s, s == FRESH_SEEDS[0]) for n in TEST_DEFENSES for d in DOMAINS
             for v in list(VARIANTS) + [None] for s in FRESH_SEEDS]
    df, series = _run(tasks, workers, "test")
    df.to_csv(path, index=False)
    with open(os.path.join(out, "test_timeseries.pkl"), "wb") as f:
        pickle.dump(series, f)


def stage_export(out):
    """Export the selected v2.1 model and knobs for the Ryu testbed."""
    models, taus = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    sel = json.load(open(os.path.join(out, "selected.json")))["selected"]
    m = models[sel["detector"]]
    idx = m.idx if isinstance(m, SubsetModel) else None
    base = m.m if isinstance(m, SubsetModel) else m
    pol = _policy(sel)
    ed = os.path.join(out, "exported")
    os.makedirs(ed, exist_ok=True)
    for d in DOMAINS:
        _dump(ed, f"v21_{d}.json", dict(
            weights=[w.tolist() for w in base.get_weights()], mean=base.scaler.mean.tolist(),
            std=base.scaler.std.tolist(), tau=taus[f"{sel['detector']}/{d}"],
            feature_idx=idx, features=FEATURE_NAMES, rho=pol["rho"], t_short=int(pol["t_short"]),
            h_crit=pol["h_crit"] if pol["hard"] else 2.0, target=0.80))


def stage_report(out):
    from . import report as R
    R.LABEL.update({"v2": "FL-DualGuard v2", "v2.1": "FL-DualGuard v2.1 (ours)",
                    "dg-local-noctx": "Local MLP (no ctx) + v2.1 policy"})
    R.PROPOSED = "v2.1"
    df = pd.read_csv(os.path.join(out, "test_episodes.csv"))
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    cols = ["defense", "episodes"] + [lab for _, lab, _ in R.METRICS]
    R.summarize(df, TEST_DEFENSES)[cols].to_csv(os.path.join(tdir, "table_test_attack.csv"), index=False)
    R.summarize(df[df.variant == "benign"], TEST_DEFENSES, attack_only=False)[cols].to_csv(
        os.path.join(tdir, "table_test_benign_only.csv"), index=False)
    R.summarize(df[df.variant == "A6"], TEST_DEFENSES)[cols].to_csv(
        os.path.join(tdir, "table_test_unseen_A6.csv"), index=False)
    att = df[df.variant != "benign"]
    tests = pd.concat([R.paired_tests(att, m, TEST_DEFENSES) for m in
                       ("benign_flows_impacted_frac", "avg_attack_occ_post",
                        "overflow_seconds_post_attack")])
    tests.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)
    (att.pivot_table(index="defense", columns="variant", values="benign_flows_impacted_frac") * 100) \
        .round(2).to_csv(os.path.join(tdir, "table_test_by_variant.csv"))
    _figure(out, att, R)
    print(R.summarize(df, TEST_DEFENSES)[cols].to_string(index=False))
    print(tests.round(4).to_string(index=False))


def _figure(out, att, R):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    R._style(plt)
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    variants = sorted(att.variant.unique())
    show = (("dms-btt", R.AQUA), ("dg-local-noctx", R.ORANGE), ("v2", R.GRAY), ("v2.1", R.BLUE))
    g = att.pivot_table(index="defense", columns="variant", values="benign_flows_impacted_frac") * 100
    fig, ax = plt.subplots(figsize=(8, 2.9))
    w = 0.2
    for i, (d, col) in enumerate(show):
        ax.bar(np.arange(len(variants)) + (i - 1.5) * w, g.loc[d, variants], width=w - 0.03,
               color=col, label=R.LABEL[d])
    ax.set_xticks(range(len(variants)), variants)
    ax.set_ylabel("Benign flows impacted (%)")
    ax.set_title("Fresh seeds 5000-5009 (one-shot test)", fontsize=9, loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=7.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, "figures", f"fig7_v21_per_variant.{ext}"))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v2")
    ap.add_argument("--out", default="results/v21")
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
        stage_select(a.src, a.out, a.workers)
    if "test" in st:
        stage_test(a.src, a.out, a.workers)
    if "export" in st:
        stage_export(a.out)
    if "report" in st:
        stage_report(a.out)


if __name__ == "__main__":
    main()
