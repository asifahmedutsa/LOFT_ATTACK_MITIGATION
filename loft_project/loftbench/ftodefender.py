"""FTODefender (Tang et al., ESWA 2024) for the T1B testbed comparison: trained on T1A exactly like
the other baselines (training runs A1-A3 + benign, seeds 1000-1004), then checked in the simulator
on T1B development seeds before any testbed run.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.ftodefender collect|train|check

collect  per poll of every T1A training run: flow count, source entropy, new sources, attack flag
train    benign benchmark window, detection features and CRITIC weights; LightGBM-LR on the rule
         features; exports results/v21/exported/ftod_rule_T1B.json (checked against the Python
         model) and ftod_config_T1B.json
check    simulator T1B at 600 pps, development seeds 2000-2002, A2 / A4 / E9P / benign: detection
         score distribution, harm, attack occupancy, blocks (results/ftodefender/check.md)
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import dataclasses  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from . import testbed_baselines as TB  # noqa: E402
from .baselines import FTODDetector, FTODefender, _entropy, critic_weights, edr, ftod_rule_features  # noqa: E402
from .config import SimConfig, VARIANTS, attack_variant  # noqa: E402
from .experiment import COLLECT_CFG, SPLITS  # noqa: E402
from .lgbjson import LGBMLRJSON  # noqa: E402
from .sim import run_episode  # noqa: E402
from .trace import TRACE_DOMAIN_IDX, TRACE_DOMAINS  # noqa: E402
from .traffic import build_traffic  # noqa: E402

OUT = "results/ftodefender"
EXP = "results/v21/exported"
LIB = ["A1", "A2", "A3"]
WINDOW, EPS_FRAC, CAP = 10, 0.05, 3500


def _seq_task(args):
    v, s = args
    prof, idx = TB.profile_of("T1A")
    tr = build_traffic(prof, idx, VARIANTS[v] if v else None, s, COLLECT_CFG.duration, COLLECT_CFG.attack_start)
    rows, seen = [], set()

    def hook(tt, fids, obs, lab):
        src = tr.flow_src[obs["fids"]]
        u = set(np.unique(src).tolist())
        new = len(u - seen)
        seen.update(u)
        on = v is not None and any(a <= tt <= b + 1e-9 for a, b in tr.attack_active)
        rows.append((tt, obs["count"], _entropy(src) if len(src) else 0.0, new, int(on)))

    run_episode(tr, COLLECT_CFG, collect=hook, record_ts=False)
    return v, s, np.array(rows)


def stage_collect():
    os.makedirs(OUT, exist_ok=True)
    tasks = [(v, s) for v in LIB + [None] for s in SPLITS["train"]]
    with get_context("fork").Pool(4) as p:
        seqs = {(v, s): r for v, s, r in p.imap_unordered(_seq_task, tasks)}
    pickle.dump(seqs, open(f"{OUT}/t1a_seqs.pkl", "wb"))
    print({f"{k}": len(r) for k, r in seqs.items()})


def _features(seq, benchmark, eps):
    """Detection features for every poll of one run, as FTODDetector computes them online."""
    out = []
    for i in range(len(seq)):
        c = seq[max(0, i - WINDOW + 1):i + 1, 1]
        g = seq[max(0, i - WINDOW + 1):i + 1, 3]
        out.append((edr(c, benchmark, eps), seq[i, 2], float(g.std(ddof=1)) if len(g) > 1 else 0.0, seq[i, 4]))
    return np.array(out)


def stage_train():
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression

    from . import v5
    from .lgbjson import export, leaves, onehot
    seqs = pickle.load(open(f"{OUT}/t1a_seqs.pkl", "rb"))
    eps = EPS_FRAC * CAP
    ben = seqs[(None, SPLITS["train"][0])]
    k = int(np.searchsorted(ben[:, 0], 60.0))
    benchmark = ben[k:k + WINDOW, 1]                 # 10 polls of benign traffic in steady state
    F = np.concatenate([_features(r, benchmark, eps) for r in seqs.values()])
    w, fmax, fmin = critic_weights(F[:, :3])
    tr, _ = v5._t1a()
    X, y = ftod_rule_features(tr.X), tr.y
    gbm = lgb.LGBMClassifier(n_estimators=100, random_state=0, n_jobs=4, verbose=-1).fit(X, y)
    width = int(max(t["num_leaves"] for t in gbm.booster_.dump_model()["tree_info"]))
    lr = LogisticRegression(max_iter=2000).fit(onehot(leaves(gbm.booster_, X), width), y)
    rng = np.random.default_rng(0)
    err = export(gbm, lr, f"{EXP}/ftod_rule_T1B.json", X[rng.choice(len(X), 3000, replace=False)])
    cfg = dict(weights=w.tolist(), fmax=fmax.tolist(), fmin=fmin.tolist(), benchmark=benchmark.tolist(), eps=eps,
               window=WINDOW, th1=0.65, th2=0.5, min_evict=20)
    json.dump(cfg, open(f"{EXP}/ftod_config_T1B.json", "w"), indent=1)
    ds = FTODefender(None, None, w, fmax, fmin).score
    S = np.array([ds(f) for f in F[:, :3]])
    info = dict(parity_max_abs_diff=err, weights=w.tolist(), rows=int(len(y)), polls=int(len(F)),
                ds_benign_mean=float(S[F[:, 3] == 0].mean()), ds_attack_mean=float(S[F[:, 3] == 1].mean()),
                benign_polls_below_th1=float((S[F[:, 3] == 0] < 0.65).mean()),
                attack_polls_below_th1=float((S[F[:, 3] == 1] < 0.65).mean()))
    json.dump(info, open(f"{OUT}/train_info.json", "w"), indent=1)
    print(json.dumps(info, indent=1))
    assert err < 1e-6, err


def make(cfg=None):
    cfg = cfg or json.load(open(f"{EXP}/ftod_config_T1B.json"))
    return FTODefender(LGBMLRJSON(f"{EXP}/ftod_rule_T1B.json"), FTODDetector(cfg["benchmark"], cfg["eps"], cfg["window"]),
                       cfg["weights"], cfg["fmax"], cfg["fmin"], th1=cfg["th1"], th2=cfg["th2"],
                       min_evict=cfg["min_evict"])


def _check_task(args):
    v, s = args
    prof = dataclasses.replace(TRACE_DOMAINS["T1B"], rate_pps=600.0)
    tr = build_traffic(prof, TRACE_DOMAIN_IDX["T1B"], None if v == "benign" else attack_variant(v), s, 300.0, 50.0)
    d = make()
    ds = []
    orig = d.on_poll

    def on_poll(t, obs):
        out = orig(t, obs)
        ds.append((t, d.last_ds))
        return out
    d.on_poll = on_poll
    res = run_episode(tr, SimConfig(duration=300.0), defense=d, record_ts=False)
    att = set(np.unique(tr.flow_src[tr.flow_attack]).tolist()) if v != "benign" else set()
    return v, s, res.summary, np.array(ds), len(d.blocked & att), len(d.blocked - att)


def stage_check():
    tasks = [(v, s) for v in ("A2", "A4", "E9P", "benign") for s in (2000, 2001, 2002)]
    with get_context("fork").Pool(4) as p:
        res = list(p.imap_unordered(_check_task, tasks))
    L = ["# FTODefender check (simulator T1B, 600 pps, development seeds 2000-2002)", "",
         "| Traffic | Seed | Harm % | Attack occupancy % | Polls with DS < 0.65 after 50 s | Sources blocked (attack / benign) |",
         "|---|---|---|---|---|---|"]
    for v, s, sm, ds, ab, bb in sorted(res, key=lambda r: (r[0], r[1])):
        after = ds[ds[:, 0] >= 50, 1] if len(ds) else np.array([])
        L.append(f"| {v} | {s} | {100 * sm['benign_flows_harmed_frac']:.2f} | {100 * sm.get('avg_attack_occ_post', 0):.1f} | "
                 f"{100 * (after < 0.65).mean() if len(after) else 0:.0f} % | {ab} / {bb} |")
    open(f"{OUT}/check.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"collect": stage_collect, "train": stage_train, "check": stage_check}[sys.argv[1]]()
