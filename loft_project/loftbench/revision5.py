"""Revision 5: the main comparison on real background traffic (experiment E2).

    python -m loftbench.revision5 --out results/revision5 --stages prereg,collect,train,test,report

Ten of the twelve related papers replay a real trace as background traffic: IMC-10
(univ1/univ2) or bigFlows.pcap (DMS-BTT). Every earlier result here used synthetic domains.
This study replays bigFlows (T1, at DMS-BTT's 1,200 pps) and IMC-10 univ2 (T2 at FTOP's
1,000 pps, T3 at its native 9,000 pps) as the benign traffic of three new domains, in the DMS-BTT port topology, with the
same generated attacks.

Methods (nothing is selected on test data; the only fitting on the traces is calibration and
the baselines' local training, all on training/validation seeds):
  none           no defense
  dms-blocklist  DMS-BTT tuned + blocklist (revision 2, family B knobs), its CatBoost state and
                 flow models trained locally on the trace with its own published attack
                 settings A1-A3 (training seeds)
  local-lib      a local MLP (same 17 features) trained on the trace with the public attack
                 library A1-A3, v2.1 policy, threshold calibrated on the trace's validation benign
  v2.1           FL-DualGuard v2.1 transferred: the federated detector trained on D1-D3 only,
                 threshold re-calibrated on the trace's validation benign (1 % budget); no retraining
  v2.1+pfs4b     v2.1 with PortGuard as selected in step 4b (gated, weighted shares, q 0.90)

Test: fresh seeds 9000-9009 (never used), attacks A1-A7 and the refresh-gap sweep of step 4.
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

from .config import VARIANTS, SimConfig
from .data import Dataset, collect_run, profile_of
from .defenses import DMSBTT, DualGuard, PortGuard
from .experiment import BUDGET, COLLECT_CFG, EPOCHS, SPLITS, _dump, _train_dms
from .models import threshold_at_fpr, train_local
from .ports import assign_ports
from .revision1 import cluster_boot, cluster_wilcoxon
from .revision4 import ATTACKS, FAST_KEYS, GAP_KEYS, GAPS, STANDARD
from .sim import Defense, run_episode
from .trace import TRACE_DOMAINS
from .traffic import build_traffic

TRACES = ["T1", "T2", "T3"]
LIB = ["A1", "A2", "A3"]                       # DMS-BTT's published settings
TEST_SEEDS = list(range(9000, 9010))
CFG = SimConfig(duration=300.0)
DEFENSES = ["none", "dms-blocklist", "local-lib", "v2.1", "v2.1+pfs4b"]
HYPOTHESES = dict(
    H1="traces, A1-A7: v2.1 (transferred, recalibrated only) harms fewer benign flows than "
       "DMS-BTT tuned + blocklist trained on the trace (cluster Wilcoxon over (trace, seed), Holm)",
    H2="traces, A1-A7: v2.1 transferred is non-inferior to local-lib trained on the trace "
       "(mean harm difference <= 0.5 points)",
    H3="each trace, A1-A7: v2.1 transferred harms <= 3 % of benign flows on average",
    H4="traces, gaps <= 1 s: v2.1+pfs4b harms fewer benign flows than v2.1",
    H5="traces, A1-A7: v2.1+pfs4b is non-inferior to v2.1 (<= 0.5 points)",
)
_CTX = {}


# ---------------------------------------------------------------- prereg
def stage_prereg(out, src, rev2, rev4b):
    path = os.path.join(out, "preregistration.json")
    if os.path.exists(path):
        print("preregistration exists; leaving it unchanged")
        return
    files = {t: TRACE_DOMAINS[t].file for t in TRACES}
    _dump(out, "preregistration.json", dict(
        created_utc=datetime.now(timezone.utc).isoformat(), traces=dict(
            T1=dict(trace="bigFlows.pcap", rate_pps=TRACE_DOMAINS["T1"].rate_pps, file=files["T1"]),
            T2=dict(trace="IMC-10 univ2 (first 3,000,000 packets of univ2_pt1)",
                    rate_pps=TRACE_DOMAINS["T2"].rate_pps, file=files["T2"], note="FTOP's rate"),
            T3=dict(trace="same univ2 window", rate_pps=TRACE_DOMAINS["T3"].rate_pps, file=files["T3"],
                    note="native rate")),
        defenses=DEFENSES, library=LIB, hypotheses=HYPOTHESES,
        fixed=dict(v21=f"{src} + results/v21 (fedavg, rho 0.7, t_short 1 s, no hard guard)",
                   dms_blocklist=json.load(open(os.path.join(rev2, "selected.json")))["selected"]["B"],
                   pfs4b=json.load(open(os.path.join(rev4b, "selected.json")))["selected"]),
        ports="dedicated (DMS-BTT topology; trace flows anchored to their client host)",
        train_seeds=list(SPLITS["train"]), val_seeds=list(SPLITS["val"]), test_seeds=TEST_SEEDS,
        attacks=STANDARD + GAP_KEYS, gaps_s=GAPS, calibration_budget=BUDGET,
        primary_metric="benign_flows_harmed_frac",
        statistics="cluster bootstrap and cluster Wilcoxon over (trace, seed); Holm across H1, H4",
        also_reported="DMS-BTT Table 6 format: average and max attack share, average table usage, "
                      "earliest overflow, total overflow time, Packet-In and TABLE_FULL counts"))
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(os.path.join(out, "preregistration.sha256"), "w").write(h + "\n")
    print("preregistered", h[:16])


# ---------------------------------------------------------------- collect
def _collect(args):
    t, v, s = args
    return t, v, s, collect_run(t, v, s, COLLECT_CFG)


def stage_collect(out, workers):
    tasks = [(t, v, s) for t in TRACES for v in LIB + [None] for s in SPLITS["train"]]
    tasks += [(t, None, s) for t in TRACES for s in SPLITS["val"]]
    runs = {}
    with get_context("fork").Pool(workers) as p:
        for t, v, s, ds in p.imap_unordered(_collect, tasks):
            runs[(t, v, s)] = ds
    with open(os.path.join(out, "trace_runs.pkl"), "wb") as f:
        pickle.dump(runs, f)
    print("collected", len(runs), "runs")


# ---------------------------------------------------------------- train
def stage_train(out, src):
    runs = pickle.load(open(os.path.join(out, "trace_runs.pkl"), "rb"))
    v21, v21_taus = pickle.load(open(os.path.join(src, "models.pkl"), "rb"))
    m, taus, info = {"fedavg": v21["fedavg"]}, {}, {}
    for t in TRACES:
        tr = Dataset.concat([runs[(t, v, s)] for v in LIB + [None] for s in SPLITS["train"]])
        va = Dataset.concat([runs[(t, None, s)] for s in SPLITS["val"]])
        m[f"dms_state/{t}"], m[f"dms_flow/{t}"] = _train_dms(tr)
        m[f"local-lib/{t}"] = train_local(tr.X, tr.y, epochs=EPOCHS)
        ben = va.X[va.y == 0]
        taus[f"fedavg/{t}"] = threshold_at_fpr(m["fedavg"].predict_proba(ben), BUDGET)
        taus[f"local-lib/{t}"] = threshold_at_fpr(m[f"local-lib/{t}"].predict_proba(ben), BUDGET)
        info[t] = dict(train_rows=int(len(tr.y)), train_attack_rows=int(tr.y.sum()),
                       val_benign_rows=int(len(ben)), tau_fedavg=float(taus[f"fedavg/{t}"]),
                       tau_local_lib=float(taus[f"local-lib/{t}"]))
    info["tau_fedavg_synthetic"] = {k: float(v) for k, v in v21_taus.items() if k.startswith("fedavg/")}
    with open(os.path.join(out, "models.pkl"), "wb") as f:
        pickle.dump((m, taus), f)
    _dump(out, "train_info.json", info)
    print(json.dumps(info, indent=1))


# ---------------------------------------------------------------- test
V21_POLICY = dict(rho=0.7, t_short=1.0, hard=False)


def make(name, t):
    m, taus, B, P = _CTX["m"], _CTX["taus"], _CTX["B"], _CTX["P"]
    if name == "none":
        return Defense()
    if name == "dms-blocklist":
        return DMSBTT(m[f"dms_state/{t}"], m[f"dms_flow/{t}"], h1=B["h1"], h2=B["h2"], p_thresh=B["p"],
                      numb_mode=B["numb"], blocklist_s=B["block"])
    if name == "local-lib":
        return DualGuard(m[f"local-lib/{t}"], taus[f"local-lib/{t}"], **V21_POLICY)
    dg = DualGuard(m["fedavg"], taus[f"fedavg/{t}"], **V21_POLICY)
    if name == "v2.1":
        return dg
    if name == "v2.1+pfs4b":
        k = {x: P[x] for x in ("mode", "share", "q", "rho_q", "hold_s", "tau_s")}
        return PortGuard(dg, name=name, **k)
    raise ValueError(name)


def _episode(args):
    name, t, v, s = args
    prof, idx = profile_of(t)
    tr = assign_ports(build_traffic(prof, idx, ATTACKS[v] if v else None, s, CFG.duration,
                                    CFG.attack_start), "dedicated")
    r = run_episode(tr, CFG, make(name, t), record_ts=True)
    occ = np.array([x["occupancy"] for x in r.timeseries])
    span = CFG.duration - CFG.attack_start
    return dict(defense=name, domain=t, variant=v or "benign", seed=s,
                avg_table_usage=float(occ.mean()), packet_in_per_s=r.summary["packet_in"] / CFG.duration,
                attack_pps=r.summary["attack_pkts"] / span, **r.summary)


def stage_test(out, workers):
    path = os.path.join(out, "test_episodes.csv")
    if os.path.exists(path):
        raise SystemExit("test already run once; refusing to rerun")
    tasks = [(n, t, v, s) for n in DEFENSES for t in TRACES for v in STANDARD + GAP_KEYS + [None]
             for s in TEST_SEEDS]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(workers) as p:
        for i, row in enumerate(p.imap_unordered(_episode, tasks, chunksize=2)):
            rows.append(row)
            if (i + 1) % 200 == 0:
                print(f"  [test] {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _load(out, rev2, rev4b):
    _CTX["m"], _CTX["taus"] = pickle.load(open(os.path.join(out, "models.pkl"), "rb"))
    _CTX["B"] = json.load(open(os.path.join(rev2, "selected.json")))["selected"]["B"]
    _CTX["P"] = json.load(open(os.path.join(rev4b, "selected.json")))["selected"]


# ---------------------------------------------------------------- report
LABEL = {"none": "No defense", "dms-blocklist": "DMS-BTT tuned + blocklist (trained on trace)",
         "local-lib": "Local MLP + public library (trained on trace)",
         "v2.1": "FL-DualGuard v2.1 (transferred)", "v2.1+pfs4b": "v2.1 + PortGuard (step 4b)"}


def stage_report(out):
    from .report import holm
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    df = pd.read_csv(os.path.join(out, "test_episodes.csv"))
    att = df[df.variant != "benign"]
    std, fast = att[att.variant.isin(STANDARD)], att[att.variant.isin(FAST_KEYS)]
    rows = []
    for t in TRACES + ["both"]:
        g0 = std if t == "both" else std[std.domain == t]
        for n in DEFENSES:
            g = g0[g0.defense == n]
            mu, lo, hi = cluster_boot(g, "benign_flows_harmed_frac")
            first = g.first_overflow_s.dropna()
            rows.append({"trace": t, "method": LABEL[n],
                         "harmed (%)": f"{100 * mu:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]",
                         "avg Pa (%)": round(100 * g.avg_attack_occ_post.mean(), 2),
                         "max Pa (%)": round(100 * g.max_attack_occ.mean(), 2),
                         "avg table usage (%)": round(100 * g.avg_table_usage.mean(), 2),
                         "earliest overflow (s)": round(first.min(), 1) if len(first) else "none",
                         "overflow time (s)": round(g.overflow_seconds_post_attack.mean(), 2),
                         "Packet-In": int(g.packet_in.mean()), "TABLE_FULL": int(g.table_full.mean())})
    pd.DataFrame(rows).to_csv(os.path.join(tdir, "table_main_dmsbtt_format.csv"), index=False)
    (att.pivot_table(index=["domain", "variant"], columns="defense", values="benign_flows_harmed_frac")
     * 100).round(2).reindex(columns=DEFENSES).rename(columns=LABEL) \
        .to_csv(os.path.join(tdir, "table_by_variant.csv"))
    ben = df[df.variant == "benign"].groupby(["domain", "defense"]).benign_flows_harmed_frac.mean()
    (100 * ben).round(3).unstack().rename(columns=LABEL).to_csv(os.path.join(tdir, "table_benign_only.csv"))

    M = "benign_flows_harmed_frac"
    spec = [("H1", std, "v2.1", "dms-blocklist"), ("H2", std, "v2.1", "local-lib"),
            ("H4", fast, "v2.1+pfs4b", "v2.1"), ("H5", std, "v2.1+pfs4b", "v2.1")]
    tests = []
    for h, g, a, b in spec:
        md, w, l, p = cluster_wilcoxon(g, M, a, b)
        tests.append(dict(hypothesis=h, a=LABEL[a], b=LABEL[b], mean_cluster_diff_points=100 * md,
                          a_wins=w, a_losses=l, p=p))
    t = pd.DataFrame(tests)
    sig = t.hypothesis.isin(["H1", "H4"])
    t.loc[sig, "p_holm"] = holm(t.loc[sig, "p"].values)
    t.to_csv(os.path.join(tdir, "hypothesis_tests.csv"), index=False)
    r = t.set_index("hypothesis")
    per_trace = std[std.defense == "v2.1"].groupby("domain")[M].mean() * 100
    outcome = dict(
        H1=bool(r.loc["H1", "p_holm"] < 0.05 and r.loc["H1", "mean_cluster_diff_points"] < 0),
        H2=bool(r.loc["H2", "mean_cluster_diff_points"] <= 0.5),
        H3=bool((per_trace <= 3.0).all()), H3_per_trace=per_trace.round(3).to_dict(),
        H4=bool(r.loc["H4", "p_holm"] < 0.05 and r.loc["H4", "mean_cluster_diff_points"] < 0),
        H5=bool(r.loc["H5", "mean_cluster_diff_points"] <= 0.5))
    _dump(out, "outcomes.json", outcome)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for f in ("hypothesis_tests.csv", "table_main_dmsbtt_format.csv", "table_benign_only.csv"):
        print("==", f)
        print(pd.read_csv(os.path.join(tdir, f)).to_string(index=False))
    print(json.dumps(outcome, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results/v21")
    ap.add_argument("--rev2", default="results/revision2")
    ap.add_argument("--rev4b", default="results/revision4b")
    ap.add_argument("--out", default="results/revision5")
    ap.add_argument("--stages", default="prereg,collect,train,test,report")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    st = a.stages.split(",")
    if "prereg" in st:
        stage_prereg(a.out, a.src, a.rev2, a.rev4b)
    if "collect" in st:
        stage_collect(a.out, a.workers)
    if "train" in st:
        stage_train(a.out, a.src)
    if "test" in st:
        _load(a.out, a.rev2, a.rev4b)
        stage_test(a.out, a.workers)
    if "report" in st:
        stage_report(a.out)


if __name__ == "__main__":
    main()
