"""Baselines retrained on the testbed (docs/final_campaign_prereg.md, section 4): each baseline's own
features and models, with the settings loftbench.v5 and loftbench.ftodefender use on simulator T1A
rows, here on the testbed recordings of FEVER's training: C3's network (T1A, seeds 4170-4172, benign,
A3 and A7) for the main arm, C1-C3 pooled for the data-matched arm.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_train_baselines table   # per-poll table rows
    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_train_baselines train   # models and exports

Entry rows (the rule classifiers, DMS-BTT's flow model): results/tbfl/rows.pkl, as FEVER's detector.
Table rows (FTMaster's and FTOP's state models, DMS-BTT's state model, FTODefender's detector): one per
poll and switch, from the entry logs, with the table features the controller computes. The label is
the simulator's "attack active" (loftbench.traffic, attack_active): the testbed replays the episode
build_traffic generates, so each attacker's intervals are taken from it and moved to the controller's
clock by the offset between the attacker's first packets there and in the truth file (t_first; the
offset is the same for every flow of an attacker, spread 0.000 s on the four recordings checked, and
the schedule does not depend on the benign scale). DMS-BTT's state 2 (active after overflow) as in loftbench.data: from the first
active poll with the table >= 99 % full or a new TABLE_FULL error, until the attack is inactive.
FTODefender's benchmark window: 10 polls of s11 from 60 s of the T1A benign recording of seed 4173
(validation, where the preregistration sets knobs); th1, th2 and min_evict as before.
Exports: results/tbfl/baselines_tb/{c3,pool}/, under the T1B file names the controller loads. Nothing in
results/v21/exported is replaced here; that is decided by the fidelity rule (section 4).
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv  # noqa: E402
import dataclasses  # noqa: E402
import gc  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "testbed"))
import entrylog  # noqa: E402

from .baselines import (_entropy, critic_weights, flora_rule_features, ftmaster_rule_features,  # noqa: E402
                        ftmaster_table_features, ftod_rule_features, ftop_rule_features, ftop_table_features)
from .config import attack_variant  # noqa: E402
from .data import Dataset, profile_of  # noqa: E402
from .features import FeatureTracker  # noqa: E402
from .ports import assign_ports  # noqa: E402
from .traffic import build_traffic  # noqa: E402
from .tbfl import CTRL, OUT, RUNS, SWITCHES, TAG, TRAIN, VAL, train_rows  # noqa: E402

CAP = 3500
BSCALE = {"T1A": 0.5}
ARMS = {"c3": ["C3"], "pool": list(CTRL)}
DST = f"{OUT}/baselines_tb"
# Table row columns.
FTM, FTOP, FN, APIT, ST, CNT, ENT, NEW, T, ON = slice(0, 8), slice(8, 12), 12, 13, 14, 15, 16, 17, 18, 19


def _active(d, dom, v, s, t0, duration=300.0, start=50.0):
    """The attack's active intervals on the controller's clock (see the module docstring)."""
    prof, idx = profile_of(dom)
    # The benign scale of the recordings (testbed/record_tbtrain.sh): 0.5 for T1A; the replay must fit
    # 300 s, and the attack schedule does not depend on it.
    f = "new_flow_rate" if hasattr(prof, "new_flow_rate") else "rate_pps"
    prof = dataclasses.replace(prof, **{f: BSCALE.get(dom, 1.0) * getattr(prof, f)})
    tr = assign_ports(build_traffic(prof, idx, attack_variant(v), s, duration, start), "dedicated")
    groups, cur = [], []
    for a, b in tr.attack_active:            # attacker 0's intervals, then attacker 1's
        cur.append((a, b))
        if b >= duration - 1e-9:
            groups.append(cur)
            cur = []
    out = []
    for j, iv in enumerate(groups):
        keep = tr.flow_port[tr.pkt_fid] == 4 + j
        sim0 = float(tr.pkt_t[keep].min())
        tb0 = min(float(r["t_first"]) for r in csv.DictReader(open(f"{d}/truth_d1h{5 + j}.csv"))) - t0
        out += [(a + tb0 - sim0, b + tb0 - sim0) for a, b in iv]
    return out


def _table(args):
    """Table rows of one recording: {switch: array (polls x 20)}."""
    d, dom, v, s = args
    t0 = float(open(f"{d}/controller_{dom}_t0.txt").read())
    act = [] if v == "benign" else _active(d, dom, v, s, t0)
    out = {}
    for sw in SWITCHES:
        base = f"{d}/switch_{dom}_{sw}"
        src, _, _ = entrylog.load_keys(base + "_keys.csv")
        sc = np.genfromtxt(base + ".csv", delimiter=",", names=True)
        tr = FeatureTracker(len(src), src, CAP, 1.0)
        seen, over, prev_full, rows = set(), False, 0.0, []
        for t, fids, pk, by, inst, installs in entrylog.read_entries(base + "_entries.bin"):
            _, _, st = tr.observe(t, fids, pk, by, inst, installs)
            obs = dict(count=len(fids), capacity=CAP, fids=fids, pkts=pk, bytes=by, install_t=inst)
            on = any(a <= t <= b + 1e-9 for a, b in act)
            i = np.searchsorted(sc["t"], t + 0.5, "right") - 1     # the switch's poll row (same clock)
            full = float(sc["table_full"][i]) if i >= 0 else 0.0
            if not on:
                over = False
            elif len(fids) >= 0.99 * CAP or full > prev_full:
                over = True
            prev_full = full
            u = np.unique(src[fids])
            new = len(set(u.tolist()) - seen)
            seen.update(u.tolist())
            rows.append(np.r_[ftmaster_table_features(t, obs, src), ftop_table_features(obs), st["FN"], st["APIT"],
                              0 if not on else (2 if over else 1), len(fids),
                              _entropy(src[fids]) if len(fids) else 0.0, new, t, int(on)])
        out[sw] = np.array(rows, np.float64)
    return (dom, None if v == "benign" else v, s), dict(out, active=act)


def stage_table():
    pat = re.compile(rf"{TAG}_(\w+?)_(A\d|E9P|benign)_none_s(\d+)$")
    doms = {dom for dom, _ in CTRL.values()}
    tasks = []
    for d in sorted(glob.glob(os.path.join(RUNS, f"{TAG}_*_none_s*"))):
        m = pat.search(os.path.basename(d))
        if m and m.group(1) in doms and int(m.group(3)) in TRAIN + VAL and os.path.exists(f"{d}/summary.txt"):
            tasks.append((d, m.group(1), m.group(2), int(m.group(3))))
    t0 = time.time()
    with get_context("fork").Pool(4) as p:
        tab = dict(p.map(_table, tasks, chunksize=1))
    os.makedirs(DST, exist_ok=True)
    pickle.dump(tab, open(f"{OUT}/table_rows.pkl", "wb"))
    info = {f"{k[0]}/{k[1]}/{k[2]}": dict({sw: dict(polls=len(r[sw]), active=int(r[sw][:, ON].sum()),
                                                   after_overflow=int((r[sw][:, ST] == 2).sum())) for sw in SWITCHES},
                                          active=[[round(a, 1), round(b, 1)] for a, b in r["active"]])
            for k, r in sorted(tab.items(), key=lambda kv: str(kv[0]))}
    json.dump(info, open(f"{DST}/table_info.json", "w"), indent=1)
    print(f"{len(tasks)} recordings in {time.time() - t0:.0f} s")


def _keys(ctrl):
    return [(CTRL[c][0], v, s) for c in ctrl for v in CTRL[c][1] + [None] for s in TRAIN]


def _ftod_seq(a):
    """FTODefender's per-poll sequence (t, count, entropy, new sources, attack flag)."""
    return a[:, [T, CNT, ENT, NEW, ON]]


def stage_train(arms):
    import lightgbm as lgb
    from catboost import CatBoostClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier

    from .cbjson import CatBoostJSON
    from .cbjson import export as cb_export
    from .experiment import _train_dms
    from .ftodefender import EPS_FRAC, WINDOW, _features
    from .lgbjson import export as lgb_export
    from .lgbjson import leaves, onehot
    from .treejson import export as tree_export

    tab = pickle.load(open(f"{OUT}/table_rows.pkl", "rb"))
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    rule = {a: Dataset.concat([train_rows(runs, c) for c in ARMS[a]]) for a in arms}
    del runs
    gc.collect()
    vb = tab[(CTRL["C3"][0], None, VAL[0])]["s11"]
    k = int(np.searchsorted(vb[:, T], 60.0))
    benchmark = vb[k:k + WINDOW, CNT]
    for arm in arms:
        t_arm = time.time()
        out = f"{DST}/{arm}"
        os.makedirs(out, exist_ok=True)
        R = rule[arm]
        parts = [tab[key][sw] for key in _keys(ARMS[arm]) for sw in SWITCHES]
        Tb = np.concatenate(parts)
        rng = np.random.default_rng(0)
        Xz = R.X[rng.choice(len(R.y), 3000, replace=False)]
        Tz = Tb[rng.choice(len(Tb), min(3000, len(Tb)), replace=False)]
        err, secs = {}, {}

        def done(name, t1):
            secs[name] = round(time.time() - t1)
            print(arm, name, secs[name], "s", flush=True)
            gc.collect()

        t1 = time.time()
        m = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4, random_state=0).fit(Tb[:, FTM], Tb[:, ON])
        err["ftmaster_state"] = tree_export(m, f"{out}/ftmaster_state_T1B.json", Tz[:, FTM])
        m = XGBClassifier(n_estimators=200, max_depth=6, n_jobs=4, random_state=0).fit(
            ftmaster_rule_features(R.X), R.y)
        err["ftmaster_rule"] = tree_export(m, f"{out}/ftmaster_rule_T1B.json", ftmaster_rule_features(Xz))
        del m
        done("ftmaster", t1)

        t1 = time.time()
        m = RandomForestClassifier(100, n_jobs=4, random_state=0).fit(Tb[:, FTOP], Tb[:, ON])
        err["ftop_state"] = tree_export(m, f"{out}/ftop_state_T1B.json", Tz[:, FTOP])
        del m
        gc.collect()
        m = RandomForestClassifier(100, min_samples_leaf=5, n_jobs=4, random_state=0).fit(
            ftop_rule_features(R.X), R.y)
        err["ftop_rule"] = tree_export(m, f"{out}/ftop_rule_T1B.json", ftop_rule_features(Xz))
        del m
        done("ftop", t1)

        t1 = time.time()
        m = CatBoostClassifier(iterations=300, random_seed=0, verbose=False, thread_count=4).fit(
            flora_rule_features(R.X), R.y)
        cb_export(m, f"{out}/flora_rule_T1B.json")
        Z = flora_rule_features(Xz)
        err["flora_rule"] = float(np.abs(CatBoostJSON(f"{out}/flora_rule_T1B.json").predict_proba(Z)[:, 1]
                                         - m.predict_proba(Z)[:, 1]).max())
        del m
        done("flora", t1)

        t1 = time.time()
        sm, fm = _train_dms(SimpleNamespace(state=Tb[:, [FN, APIT, ST]], dms=R.dms, y=R.y))
        for name, m, Z in (("dmsB_state", sm, Tz[:, [FN, APIT]]), ("dmsB_flow", fm, R.dms[rng.choice(len(R.y), 3000)])):
            cb_export(m.m, f"{out}/{name}_T1B.json")
            err[name] = float(np.abs(np.asarray(CatBoostJSON(f"{out}/{name}_T1B.json").predict_proba(Z))
                                     - np.asarray(m.m.predict_proba(Z))).max())
        del sm, fm
        done("dms-btt", t1)

        t1 = time.time()
        F = np.concatenate([_features(_ftod_seq(a), benchmark, EPS_FRAC * CAP) for a in parts])
        w, fmax, fmin = critic_weights(F[:, :3])
        Z = ftod_rule_features(R.X)
        gbm = lgb.LGBMClassifier(n_estimators=100, random_state=0, n_jobs=4, verbose=-1).fit(Z, R.y)
        width = int(max(t["num_leaves"] for t in gbm.booster_.dump_model()["tree_info"]))
        lr = LogisticRegression(max_iter=2000).fit(onehot(leaves(gbm.booster_, Z), width), R.y)
        del Z
        err["ftod_rule"] = lgb_export(gbm, lr, f"{out}/ftod_rule_T1B.json", ftod_rule_features(Xz))
        json.dump(dict(weights=w.tolist(), fmax=fmax.tolist(), fmin=fmin.tolist(), benchmark=benchmark.tolist(),
                       eps=EPS_FRAC * CAP, window=WINDOW, th1=0.65, th2=0.5, min_evict=20),
                  open(f"{out}/ftod_config_T1B.json", "w"), indent=1)
        del gbm, lr
        done("ftodefender", t1)

        info = dict(arm=arm, controllers=ARMS[arm], rule_rows=int(len(R.y)), rule_attack=int(R.y.sum()),
                    table_rows=int(len(Tb)), table_active=int(Tb[:, ON].sum()),
                    table_after_overflow=int((Tb[:, ST] == 2).sum()), ftod_weights=w.tolist(),
                    parity_max_abs_diff=err, seconds=secs, total_s=round(time.time() - t_arm))
        json.dump(info, open(f"{out}/train_info.json", "w"), indent=1)
        print(json.dumps(info, indent=1), flush=True)
        assert max(err.values()) < 1e-5, err
        del R, Tb, parts
        rule.pop(arm)
        gc.collect()


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "table":
        stage_table()
    elif st == "train":
        stage_train(sys.argv[2:] or list(ARMS))
    else:
        raise SystemExit(__doc__)
