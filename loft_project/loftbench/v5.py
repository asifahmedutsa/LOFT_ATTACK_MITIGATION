"""EnsGuard v5 (docs/v5_plan.md): the clean T1A/T1B split, then the detector candidates.

collect    T1A simulator runs as every earlier T1 training set: A1-A3 + benign x training seeds
           1000-1004 (labelled entry rows and FTMaster/FTOP table rows) and benign x validation
           seeds 2000-2002
baselines  DMS-BTT (state + flow CatBoost) and FTMaster (state + rule XGBoost) trained on T1A with
           the hyperparameters of revision 5 / testbed_baselines, exported for the testbed domain
           T1B (dmsB_*_T1B.json, ftmaster_*_T1B.json, parity checked); tau of ensguard v3 and
           v4-lite for T1B on T1A validation benign (added to their configs, T1 untouched)
cands      the four v5 detector candidates (A-D), measured on simulator T1B at the testbed's
           600 pps (development seeds 2000-2002) and on E11's unseen attack; then the rule

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.v5 {collect,baselines,cands}

Writes results/v5/ and the T1B files in results/v21/exported/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import dataclasses  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import ml_compare as M  # noqa: E402
from . import testbed_baselines as TB  # noqa: E402
from .baselines import flora_rule_features, ftmaster_rule_features, ftop_rule_features  # noqa: E402
from .config import DOMAINS, SimConfig, UNSEEN_VARIANTS, attack_variant  # noqa: E402
from .data import Dataset, collect_run  # noqa: E402
from .experiment import COLLECT_CFG, SPLITS, _train_dms  # noqa: E402
from .models import SkWrap, threshold_at_fpr  # noqa: E402
from .sim import run_episode  # noqa: E402
from .trace import TRACE_DOMAIN_IDX, TRACE_DOMAINS  # noqa: E402
from .traffic import build_traffic  # noqa: E402

OUT = "results/v5"
EXP = "results/v21/exported"
LIB = ["A1", "A2", "A3"]
VAL = (2000, 2001, 2002)
BUDGET = 0.001


def _rule_task(args):
    v, s = args
    return v, s, collect_run("T1A", v, s, COLLECT_CFG)


def stage_collect():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    tasks = [(v, s) for v in LIB + [None] for s in SPLITS["train"]] + [(None, s) for s in VAL]
    with get_context("fork").Pool(4) as p:
        runs = {(v, s): ds for v, s, ds in p.imap_unordered(_rule_task, tasks)}
        T = np.concatenate(p.map(TB._collect_task, [("T1A", v, s) for v in LIB + [None]
                                                    for s in SPLITS["train"]]))
    pickle.dump(runs, open(f"{OUT}/t1a_runs.pkl", "wb"))
    pickle.dump(T, open(f"{OUT}/t1a_table.pkl", "wb"))
    info = {f"{v}/{s}": dict(rows=int(len(d.y)), attack=int(d.y.sum())) for (v, s), d in runs.items()}
    info["table_rows"], info["seconds"] = int(len(T)), round(time.time() - t0)
    json.dump(info, open(f"{OUT}/collect_info.json", "w"), indent=1)
    print(json.dumps(info))


def _t1a():
    runs = pickle.load(open(f"{OUT}/t1a_runs.pkl", "rb"))
    tr = Dataset.concat([runs[(v, s)] for v in LIB + [None] for s in SPLITS["train"]])
    va = Dataset.concat([runs[(None, s)] for s in VAL])
    return tr, va


def stage_baselines():
    from xgboost import XGBClassifier
    from .cbjson import CatBoostJSON
    from .cbjson import export as cb_export
    from .ensjson import EnsembleJSON
    from .treejson import export as tree_export
    tr, va = _t1a()
    T = pickle.load(open(f"{OUT}/t1a_table.pkl", "rb"))
    dms_state, dms_flow = _train_dms(tr)
    ftm_state = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4, random_state=0).fit(T[:, :8], T[:, -1])
    ftm_rule = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4, random_state=0).fit(
        ftmaster_rule_features(tr.X), tr.y)
    pickle.dump(dict(dms_state=dms_state, dms_flow=dms_flow, ftmaster_state=ftm_state, ftmaster_rule=ftm_rule),
                open(f"{OUT}/baselines_t1a.pkl", "wb"))
    rng = np.random.default_rng(0)
    err = {}
    for k, m in (("dmsB_state", dms_state), ("dmsB_flow", dms_flow)):
        p = f"{EXP}/{k}_T1B.json"
        cb_export(m.m, p)
        Z = (tr.state[:, :2] if k == "dmsB_state" else tr.dms)[rng.choice(len(tr.y) if k != "dmsB_state" else len(tr.state), 3000)]
        a, b = CatBoostJSON(p).predict_proba(Z), m.m.predict_proba(Z)
        err[k] = float(np.abs(np.asarray(a) - np.asarray(b)).max())
    Tz = T[rng.choice(len(T), 3000, replace=False)]
    Xz = tr.X[rng.choice(len(tr.y), 3000, replace=False)]
    err["ftmaster_state"] = tree_export(ftm_state, f"{EXP}/ftmaster_state_T1B.json", Tz[:, :8])
    err["ftmaster_rule"] = tree_export(ftm_rule, f"{EXP}/ftmaster_rule_T1B.json", ftmaster_rule_features(Xz))
    # EnsGuard v3 and v4-lite: tau for T1B on T1A validation benign (their T1 entries unchanged).
    ben = va.X[va.y == 0]
    taus = {}
    for f in ("ens_config.json", "ens_config_v4lite.json"):
        cfg = json.load(open(f"{EXP}/{f}"))
        tau = float(threshold_at_fpr(EnsembleJSON(EXP, cfg).predict_proba(ben), cfg["budget"]))
        cfg["tau"]["T1B"], cfg["rho"]["T1B"] = tau, cfg["rho"]["T1"]
        json.dump(cfg, open(f"{EXP}/{f}", "w"), indent=1)
        taus[f] = dict(T1=cfg["tau"]["T1"], T1B=tau)
    out = dict(parity_max_abs_diff=err, taus=taus, train_rows=int(len(tr.y)), table_rows=int(len(T)),
               val_benign_rows=int(len(ben)))
    json.dump(out, open(f"{OUT}/baselines_info.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
    assert max(err.values()) < 1e-5, err


def stage_baselines2():
    """FTOP and FloRa for T1B, trained on T1A exactly as their T1 models (loftbench.testbed_baselines
    stage_train) and as DMS-BTT and FTMaster for T1B above: same rows, same settings."""
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier
    from .cbjson import CatBoostJSON
    from .cbjson import export as cb_export
    from .treejson import export as tree_export
    tr, _ = _t1a()
    T = pickle.load(open(f"{OUT}/t1a_table.pkl", "rb"))
    m = {"ftop_state": RandomForestClassifier(100, n_jobs=4, random_state=0).fit(T[:, 8:12], T[:, -1]),
         "ftop_rule": RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=0).fit(
             ftop_rule_features(tr.X), tr.y),
         "flora_rule": CatBoostClassifier(iterations=300, random_seed=0, verbose=False, thread_count=4).fit(
             flora_rule_features(tr.X), tr.y)}
    pickle.dump(m, open(f"{OUT}/baselines2_t1a.pkl", "wb"))
    rng = np.random.default_rng(0)
    Tz = T[rng.choice(len(T), min(3000, len(T)), replace=False)]
    Xz = tr.X[rng.choice(len(tr.y), 3000, replace=False)]
    err = {"ftop_state": tree_export(m["ftop_state"], f"{EXP}/ftop_state_T1B.json", Tz[:, 8:12]),
           "ftop_rule": tree_export(m["ftop_rule"], f"{EXP}/ftop_rule_T1B.json", ftop_rule_features(Xz))}
    cb_export(m["flora_rule"], f"{EXP}/flora_rule_T1B.json")
    Z = flora_rule_features(Xz)
    err["flora_rule"] = float(np.abs(CatBoostJSON(f"{EXP}/flora_rule_T1B.json").predict_proba(Z)[:, 1]
                                     - m["flora_rule"].predict_proba(Z)[:, 1]).max())
    out = dict(parity_max_abs_diff=err, train_rows=int(len(tr.y)), table_rows=int(len(T)))
    json.dump(out, open(f"{OUT}/baselines2_info.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
    assert max(err.values()) < 1e-5, err


# ---------------------------------------------------------------- candidates
def _cb(X, y, seed=0):
    from catboost import CatBoostClassifier
    return SkWrap(CatBoostClassifier(iterations=300, depth=6, verbose=0, random_seed=seed,
                                     thread_count=4).fit(X, y))


class OrDetector:
    """Evict when the federated OR the local model flags (thresholds folded in: the score is
    max(p_f / tau_f, p_l / tau_l), flagged at >= 1)."""

    def __init__(self, fed, tau_f, loc, tau_l):
        self.fed, self.tau_f, self.loc, self.tau_l = fed, tau_f, loc, tau_l

    def predict_proba(self, X):
        return np.maximum(self.fed.predict_proba(X) / self.tau_f, self.loc.predict_proba(X) / self.tau_l)


def _t1b_rows(v, seed, frac=0.05):
    """Simulator T1B rows at the testbed's 600 pps (5 % of entries per poll)."""
    prof = dataclasses.replace(TRACE_DOMAINS["T1B"], rate_pps=600.0)
    cfg = SimConfig(duration=300.0)
    tr = build_traffic(prof, TRACE_DOMAIN_IDX["T1B"], None if v == "benign" else attack_variant(v),
                       seed, cfg.duration, 50.0)
    rng = np.random.default_rng(seed)
    X, Y = [], []

    def collect(t, fids, obs, lab):
        if len(fids):
            m = rng.random(len(fids)) < frac
            X.append(obs["X"][m])
            Y.append(lab[m].astype(np.int8))
    run_episode(tr, cfg, collect=collect, record_ts=False)
    return np.concatenate(X), np.concatenate(Y)


def _rows_task(args):
    v, s = args
    return v, s, _t1b_rows(v, s)


def stage_cands():
    t0 = time.time()
    tr, va = _t1a()
    ben = va.X[va.y == 0]
    cb3 = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"].ms[1]   # v4-lite's federation
    r5 = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    t2 = Dataset.concat([r5[("T2", v, s)] for v in LIB + [None] for s in SPLITS["train"]])
    u2 = _cb(t2.X, t2.y)
    fed_c = M.Mean(cb3.ms + [u2])
    loc = _cb(tr.X, tr.y)
    print(f"models {time.time() - t0:.0f} s", flush=True)
    feds = {"A": cb3, "B": cb3, "C": fed_c, "D": fed_c}
    det, tau = {}, {}
    for k in "AC":
        det[k], tau[k] = feds[k], float(threshold_at_fpr(feds[k].predict_proba(ben), BUDGET))
    for k in "BD":
        tf = float(threshold_at_fpr(feds[k].predict_proba(ben), BUDGET / 2))
        tl = float(threshold_at_fpr(loc.predict_proba(ben), BUDGET / 2))
        det[k], tau[k] = OrDetector(feds[k], tf, loc, tl), 1.0
    # simulator T1B rows (cached)
    path = f"{OUT}/t1b_rows.pkl"
    if os.path.exists(path):
        rows = pickle.load(open(path, "rb"))
    else:
        with get_context("fork").Pool(4) as p:
            rows = {(v, s): r for v, s, r in p.imap_unordered(
                _rows_task, [(v, s) for v in ("A2", "A4", "E9P", "benign") for s in VAL])}
        pickle.dump(rows, open(path, "wb"))
    print(f"T1B rows {time.time() - t0:.0f} s", flush=True)
    # E11 unseen recall, federated part at each D controller's own 0.1 % tau
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    unseen = {}
    for k in "AC":
        rec = []
        for d in DOMAINS:
            D, V = data[("test_off", d)], data[("val", d)]
            t_d = threshold_at_fpr(feds[k].predict_proba(V.X[V.y == 0]), BUDGET)
            vrun = {r["run_id"]: r["variant"] for r in D.runs}
            var = np.array([vrun[x] for x in D.run], dtype=object)
            for v in UNSEEN_VARIANTS:
                m = (var == v) & (D.y == 1)
                rec.append(100 * float((feds[k].predict_proba(D.X[m]) >= t_d).mean()))
        unseen[k] = float(np.mean(rec))
    unseen["B"], unseen["D"] = unseen["A"], unseen["C"]
    res = []
    for k in "ABCD":
        r = dict(cand=k, tau=tau[k], unseen_recall=unseen[k])
        for v in ("A2", "A4", "E9P", "benign"):
            X = np.concatenate([rows[(v, s)][0] for s in VAL])
            y = np.concatenate([rows[(v, s)][1] for s in VAL])
            fl = det[k].predict_proba(X) >= tau[k]
            if v == "benign":
                r["fpr"] = 100 * float(fl.mean())
            else:
                r[f"recall_{v}"] = 100 * float(fl[y == 1].mean())
        res.append(r)
    t = pd.DataFrame(res)
    a2_a = float(t[t.cand == "A"].recall_A2.iloc[0])
    t["eligible"] = (t.fpr <= 0.2) & (t.unseen_recall >= 46.5) & (t.recall_A2 >= a2_a - 1)
    t["score"] = t.recall_A4 + t.recall_E9P
    ok = t[t.eligible]
    if ok.empty:
        choice = "A"
    else:
        best = ok.score.max()
        choice = ok[ok.score >= best - 2].cand.iloc[0]      # simplest first (A, B, C, D order)
    pickle.dump(dict(det=det, tau=tau, loc=loc, u2=u2, fed_c=fed_c), open(f"{OUT}/cands.pkl", "wb"))
    t.round(3).to_csv(f"{OUT}/cands.csv", index=False)
    json.dump(dict(choice=choice), open(f"{OUT}/cands.json", "w"))
    L = ["# v5 detector candidates (docs/v5_plan.md, section 2)", "",
         "Simulator T1B at 600 pps, development seeds 2000-2002 (no candidate trained on T1B); "
         "unseen = E11 A6 recall on D1-D3 test_off.", "",
         "| Candidate | recall A2 | recall A4 | recall E9P | benign FPR | unseen recall | eligible |",
         "|---|---|---|---|---|---|---|"]
    for _, r in t.iterrows():
        L.append(f"| {r.cand} | {r.recall_A2:.2f} | {r.recall_A4:.2f} | {r.recall_E9P:.2f} | {r.fpr:.3f} | "
                 f"{r.unseen_recall:.2f} | {'yes' if r.eligible else 'no'} |")
    L += ["", f"**Chosen: {choice}.**"]
    open(f"{OUT}/cands.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------- volume block (section 3)
ATT_MACS = {"00:00:00:00:01:05", "00:00:00:00:01:06"}
SWITCHES = ("s11", "s12", "s13")


def _hosts_per_poll(run, sw):
    """Per poll: table entries and per-host entries at one switch of a recorded run."""
    import glob as _g
    d = _g.glob(os.path.expanduser(f"~/loft-runs/{run}"))[0]
    s = pd.read_csv(f"{d}/switch_T1A_{sw}.csv")
    m = pd.read_csv(f"{d}/switch_T1A_{sw}_macs.csv")
    return s[["t", "entries"]], m


def _would_block(s, m, x, k=3.0, rho=0.9, cap=3500):
    """Hosts the volume rule would block (open loop): at a poll with the table >= rho full, a
    host holding more than x entries and >= k x the median host's."""
    full = set(s[s.entries >= rho * cap].t)
    out = set()
    for t, g in m[m.t.isin(full)].groupby("t"):
        e = g[g.entries > 0]
        med = float(e.entries.median()) if len(e) else 0.0
        out |= set(e[(e.entries > x) & (e.entries >= k * max(med, 1.0))].mac)
    return out


def stage_volume():
    cal = [f"v5vol_T1A_benign_none_s{s}" for s in (4150, 4151, 4152)]
    chk = [f"v5vol_T1A_{v}_none_s4153" for v in ("A2", "A4", "E9P")]
    X, rows = {}, []
    for sw in SWITCHES:
        mx = max(int(_hosts_per_poll(r, sw)[1].entries.max()) for r in cal)
        X[sw] = 1.5 * mx
        rows.append(dict(switch=sw, busiest_benign_host=mx, vol_x=X[sw]))
    res = []
    for r in cal + chk:
        blocked = set()
        for sw in SWITCHES:
            s, m = _hosts_per_poll(r, sw)
            blocked |= _would_block(s, m, X[sw])
        res.append(dict(run=r, benign_blocked=len(blocked - ATT_MACS), attackers_blocked=len(blocked & ATT_MACS)))
    t = pd.DataFrame(res)
    ok_cal = int(t[t.run.isin(cal)].benign_blocked.sum()) == 0
    ok_chk = int((t[t.run.isin(chk)].attackers_blocked == 2).sum()) >= 2
    adopt = bool(ok_cal and ok_chk)
    json.dump(dict(vol_x={"T1B": X}, adopt=adopt, calibration_ok=ok_cal, check_ok=ok_chk,
                   benign_blocked_in_attack_recordings=int(t[t.run.isin(chk)].benign_blocked.sum())),
              open(f"{OUT}/volume.json", "w"), indent=1)
    L = ["# v5 volume block (docs/v5_plan.md, section 3)", "",
         "X = 1.5 x the busiest benign host per switch in the T1A benign recordings (seeds 4150-4152); "
         "open-loop replay of the recordings (defense none).", "",
         "```", pd.DataFrame(rows).to_string(index=False), "", t.to_string(index=False), "```", "",
         f"- calibration recordings: no benign host blocked: **{ok_cal}**",
         f"- check recordings: both attackers blocked in at least 2 of 3: **{ok_chk}**",
         f"- **adopt: {'yes' if adopt else 'no'}**"]
    open(f"{OUT}/volume.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def stage_export():
    """ens_config_v5.json: v4-lite's detector (candidate A) and block rule, changed-entry scoring,
    tau for T1B from T1A, and the volume block if adopted."""
    from .ensjson import EnsembleJSON
    v4 = json.load(open(f"{EXP}/ens_config_v4lite.json"))
    ch = json.load(open(f"{OUT}/cands.json"))["choice"]
    assert ch == "A", ch
    vol = json.load(open(f"{OUT}/volume.json"))
    cfg = dict(v4, selected="v5-A" + ("+volume" if vol["adopt"] else ""))
    cfg["block"] = dict(v4["block"])
    if vol["adopt"]:
        cfg["block"]["vol_x"] = vol["vol_x"]
    tr, va = _t1a()
    tau = float(threshold_at_fpr(EnsembleJSON(EXP, cfg).predict_proba(va.X[va.y == 0]), cfg["budget"]))
    assert abs(tau - v4["tau"]["T1B"]) < 1e-12, (tau, v4["tau"]["T1B"])
    json.dump(cfg, open(f"{EXP}/ens_config_v5.json", "w"), indent=1)
    print(json.dumps(cfg, indent=1))


if __name__ == "__main__":
    {"collect": stage_collect, "baselines": stage_baselines, "baselines2": stage_baselines2, "cands": stage_cands,
     "volume": stage_volume, "export": stage_export}[sys.argv[1]]()
