"""EnsGuard v4-lite, steps 2-4 of docs/v4lite_plan.md (development data only).

models    ens (RF 50/12 + CatBoost) and cb (CatBoost only) federated over D1-D3, model seeds
          0, 1, 2 (seed 0 = the deployed v3 models, results/e3_ens/models.pkl); tau per controller
          at the 0.1 % budget on its validation benign (T1: trace validation benign, seeds
          2000-2002)
detsel    step 2: validation recall on attacks the controller did not train on (new labelled
          validation runs of the other controllers' attacks and A6 in each domain, seeds
          2000-2002), closed-loop simulator harm / occupancy / benign blocks with v3's evict-block
          setting, scoring time; then the rule
blocksel  step 3: block-rule floor grid m0 x f (+ the v3 rule) with the chosen detector, closed
          loop in the simulator and open loop on the 12 testbed entry logs; then the rule
cache     step 4: score only entries whose counters changed, measured on the testbed replay

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.v4lite {models,detsel,blocksel,cache}

Writes results/v4lite/.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import glob  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import evictblock as EB  # noqa: E402
from . import flowhold as FH  # noqa: E402
from . import ml_compare as M  # noqa: E402
from . import revision5 as R5  # noqa: E402
from .config import DOMAINS, EXPOSURE  # noqa: E402
from .data import Dataset, collect_run  # noqa: E402
from .defenses import EvictBlock, PortGuard  # noqa: E402
from .e1_pair import RF  # noqa: E402
from .experiment import COLLECT_CFG  # noqa: E402
from .models import SkWrap, threshold_at_fpr  # noqa: E402

OUT = "results/v4lite"
BUDGET = 0.001
VAL_SEEDS = (2000, 2001, 2002)
MODEL_SEEDS = (0, 1, 2)
V3_RULE = dict(n_min=50, f_min=3.0, block_s=60.0, m0=1.0, frac_min=0.0)
GRID = [dict(V3_RULE, m0=m0, frac_min=f) for m0 in (10.0, 20.0, 40.0) for f in (0.2, 0.3, 0.5)]
_G = {}


def _rf(seed):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_jobs=4, random_state=seed, **RF["rf50d12"])


def _cb(seed):
    from catboost import CatBoostClassifier
    return CatBoostClassifier(iterations=300, depth=6, verbose=0, random_seed=seed, thread_count=4)


def _local(make, X, y):
    m = SkWrap(make().fit(X, y))
    if hasattr(m.m, "n_jobs"):
        m.m.n_jobs = 1
    return m


# ---------------------------------------------------------------- models
def stage_models():
    t0 = time.time()
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    ens3 = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"]
    cands = {("ens", 0): ens3, ("cb", 0): ens3.ms[1]}
    for s in MODEL_SEEDS[1:]:
        rf = M.Mean([_local(lambda: _rf(s), data[("train", d)].X, data[("train", d)].y) for d in DOMAINS])
        cb = M.Mean([_local(lambda: _cb(s), data[("train", d)].X, data[("train", d)].y) for d in DOMAINS])
        cands[("ens", s)], cands[("cb", s)] = M.Mean([rf, cb]), cb
        print(f"model seed {s}: {time.time() - t0:.0f} s", flush=True)
    runs = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    vben = {d: data[("val", d)].X[data[("val", d)].y == 0] for d in DOMAINS}
    t1 = Dataset.concat([runs[("T1", None, s)] for s in VAL_SEEDS])
    vben["T1"] = t1.X[t1.y == 0]
    taus = {k: {d: float(threshold_at_fpr(m.predict_proba(X), BUDGET)) for d, X in vben.items()}
            for k, m in cands.items()}
    os.makedirs(OUT, exist_ok=True)
    pickle.dump(dict(cands=cands, taus=taus), open(f"{OUT}/models.pkl", "wb"))
    json.dump({f"{c}/{s}": t for (c, s), t in taus.items()}, open(f"{OUT}/taus.json", "w"), indent=1)
    print(json.dumps({f"{c}/{s}": t for (c, s), t in taus.items()}, indent=1))


def _models():
    return pickle.load(open(f"{OUT}/models.pkl", "rb"))


# ---------------------------------------------------------------- validation rows
def _collect(args):
    d, v, s = args
    return d, v, s, collect_run(d, v, s, COLLECT_CFG)


def _valrows():
    """Labelled validation runs of the attacks each controller did NOT train on (cached)."""
    path = f"{OUT}/val_remote.pkl"
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    tasks = [(d, v, s) for d in DOMAINS
             for v in sorted({x for e in EXPOSURE.values() for x in e} - set(EXPOSURE[d])) + ["A6"]
             for s in VAL_SEEDS]
    out = {}
    with get_context("fork").Pool(4) as p:
        for d, v, s, ds in p.imap_unordered(_collect, tasks):
            out[(d, v, s)] = ds
    pickle.dump(out, open(path, "wb"))
    return out


# ---------------------------------------------------------------- closed-loop simulator
def _make(key, d):
    cand, seed, rule = _G["spec"][key]
    model, tau = _G["cands"][(cand, seed)], _G["taus"][(cand, seed)][d]
    dg = FH._dg(d)
    eb = EvictBlock(model, tau, name=key, rho=dg.rho, h_crit=dg.h_crit, target=dg.target,
                    n_min=rule["n_min"], f_min=rule["f_min"], block_s=rule["block_s"],
                    m0=rule["m0"], frac_min=rule["frac_min"])
    P = R5._CTX["P"]
    return PortGuard(eb, name=key, mode="full", **{x: P[x] for x in ("share", "q", "rho_q", "hold_s", "tau_s")})


def _episode(args):
    EB._make = _make                       # evictblock's episode runner, our defenses
    return EB._episode(("dev",) + tuple(args))


def _closed_loop(spec, tag):
    path = f"{OUT}/{tag}_episodes.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    FH._load()
    M_ = _models()
    _G.update(cands=M_["cands"], taus=M_["taus"], spec=spec)
    cells = [(d, v, s) for d in EB.DOMS for v in EB.VARS for s in VAL_SEEDS]
    tasks = [(k, *c) for k in spec for c in cells]
    rows, t0 = [], time.time()
    with get_context("fork").Pool(4) as p:
        for i, r in enumerate(p.imap_unordered(_episode, tasks, chunksize=1)):
            rows.append(r)
            if (i + 1) % 45 == 0:
                print(f"  {tag}: {i + 1}/{len(tasks)} episodes, {time.time() - t0:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df


def _sim_summary(df):
    rows = []
    for k, g in df.groupby("defense"):
        a = g[g.variant != "benign"]
        rows.append(dict(key=k, harm_pct=100 * g.benign_flows_harmed_frac.mean(),
                         attack_occ_pct=100 * a.avg_attack_occ_post.mean(),
                         benign_host_blocks=int(g.benign_hosts_blocked.sum()),
                         a2_attack_hosts_blocked=float(g[g.variant == "A2"].attack_hosts_blocked.mean())))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- step 2
def stage_detsel():
    M_ = _models()
    vr = _valrows()
    rows = []
    for (c, s), m in M_["cands"].items():
        rec = []
        for d in DOMAINS:
            parts = [vr[(d, v, x)] for (dd, v, x) in vr if dd == d]
            X = np.concatenate([p.X[p.y == 1] for p in parts])
            rec.append(100 * float((m.predict_proba(X) >= M_["taus"][(c, s)][d]).mean()))
        Xt = np.random.default_rng(0).random((10000, 17))
        t0 = time.perf_counter()
        for _ in range(3):
            m.predict_proba(Xt)
        ms = 1000 * (time.perf_counter() - t0) / 3
        rows.append(dict(cand=c, seed=s, val_remote_recall=np.mean(rec), ms_per_10k=ms,
                         **{f"val_recall_{d}": r for d, r in zip(DOMAINS, rec)}))
    v = pd.DataFrame(rows)
    spec = {f"{c}-m{s}-v3rule": (c, s, V3_RULE) for c in ("ens", "cb") for s in MODEL_SEEDS}
    sim = _sim_summary(_closed_loop(spec, "detsel"))
    sim[["cand", "seed"]] = sim.key.str.extract(r"(\w+)-m(\d)-")
    sim.seed = sim.seed.astype(int)
    t = v.merge(sim, on=["cand", "seed"])
    t.round(3).to_csv(f"{OUT}/detsel.csv", index=False)
    g = t.groupby("cand")[["val_remote_recall", "harm_pct", "attack_occ_pct", "benign_host_blocks", "ms_per_10k"]]
    mean, sd = g.mean(), g.std()
    e, c = mean.loc["ens"], mean.loc["cb"]
    checks = dict(V=bool(c.val_remote_recall >= e.val_remote_recall - 2),
                  H=bool(c.harm_pct <= e.harm_pct + 0.25),
                  O=bool(c.attack_occ_pct <= e.attack_occ_pct + 1),
                  B=bool(t[t.cand == "cb"].benign_host_blocks.sum() == 0))
    chosen = "cb" if all(checks.values()) else "ens"
    json.dump(dict(checks=checks, chosen=chosen), open(f"{OUT}/detsel.json", "w"), indent=1)
    L = ["# v4-lite step 2: detector (docs/v4lite_plan.md)", "",
         "Mean (sd) over model seeds 0-2.", "",
         "| Candidate | V: recall on attacks not trained on (%) | H: harm (%) | O: attack occupancy (%) | B: benign hosts blocked | ms per 10k entries |",
         "|---|---|---|---|---|---|"]
    for k in ("ens", "cb"):
        L.append(f"| {k} | " + " | ".join(f"{mean.loc[k, x]:.2f} ({sd.loc[k, x]:.2f})" for x in
                                          ("val_remote_recall", "harm_pct", "attack_occ_pct", "benign_host_blocks", "ms_per_10k")) + " |")
    L += ["", f"Checks for cb: {checks}. **Chosen: {chosen}.**", "", "Per seed:", "", "```",
          t.round(3).to_string(index=False), "```"]
    open(f"{OUT}/detsel.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------- testbed replay (open loop)
def _replay_runs():
    sys.path.insert(0, "testbed")
    import e11_testbed as E
    return E.tb_runs(os.path.expanduser("~/loft-runs/e11tb_T1_*_none_s*"))


def _replay(model, tau, rule, run_dir, sw, cache=False, rho=0.7, capacity=3500):
    """Feed one recorded switch log to EvictBlock poll by poll; its decisions are not applied.
    Returns per host: label (1 attack, 0 benign, -1 other), blocked (bool); and timing."""
    sys.path.insert(0, "testbed")
    import entrylog
    from .features import FeatureTracker
    base = os.path.join(run_dir, f"switch_T1_{sw}")
    src, _, mac = entrylog.load_keys(base + "_keys.csv")
    hosts = sorted({x for x in mac if x})
    hidx = {h: i for i, h in enumerate(hosts)}
    other = len(hosts)
    port = np.array([hidx.get(x, other) for x in mac], int)
    eb = EvictBlock(model, tau, rho=rho, n_min=rule["n_min"], f_min=rule["f_min"], block_s=rule["block_s"],
                    m0=rule["m0"], frac_min=rule["frac_min"], exempt=(other,))
    eb.reset({"flow_port": port, "n_ports": other + 1})
    tr = FeatureTracker(len(src), src, capacity, 1.0)
    prev, last_score, t_score = {}, {}, 0.0
    flags_full, flags_cached = [], []
    for t, fids, pk, by, inst, installs in entrylog.read_entries(base + "_entries.bin"):
        X, _, _ = tr.observe(t, fids, pk, by, inst, installs)
        obs = {"capacity": capacity, "count": len(fids), "fids": fids, "X": X, "dt": 1.0}
        if cache and len(fids):
            # the reference full scores and the cached scores on the same rows (step 4)
            full = model.predict_proba(X)
            key = list(zip(pk.tolist(), by.tolist()))
            changed = np.array([prev.get(f) != k for f, k in zip(fids.tolist(), key)])
            t0 = time.perf_counter()
            sc = np.empty(len(fids))
            if changed.any():
                sc[changed] = model.predict_proba(X[changed])
            sc[~changed] = [last_score[f] for f in fids[~changed].tolist()]
            t_score += time.perf_counter() - t0
            for f, k, v in zip(fids.tolist(), key, sc.tolist()):
                prev[f], last_score[f] = k, v
            if len(fids) / capacity >= rho:
                flags_full.append(full >= tau)
                flags_cached.append(sc >= tau)
        eb.on_poll(t, obs)
    blocked = {q for _, q in eb.blocks}
    out = []
    for h, i in hidx.items():
        out.append(dict(host=h, label=1 if h in entrylog.ATTACK_MACS else 0, blocked=i in blocked))
    res = dict(hosts=out)
    if cache:
        ff = np.concatenate(flags_full) if flags_full else np.zeros(0, bool)
        fc = np.concatenate(flags_cached) if flags_cached else np.zeros(0, bool)
        res.update(n=len(ff), agree=float((ff == fc).mean()) if len(ff) else 1.0, t_cached=t_score)
    return res


def _replay_grid(model, tau, rules):
    rows = []
    for v, s, d in _replay_runs():
        for sw in ("s11", "s12", "s13"):
            for name, rule in rules.items():
                for h in _replay(model, tau, rule, d, sw)["hosts"]:
                    rows.append(dict(rule=name, variant=v, seed=s, switch=sw, **h))
    return pd.DataFrame(rows)


def _rname(r):
    return "v3rule" if r["m0"] == 1 and r["frac_min"] == 0 else f"m0{r['m0']:g}-f{r['frac_min']:g}"


# ---------------------------------------------------------------- step 3
def stage_blocksel():
    chosen = json.load(open(f"{OUT}/detsel.json"))["chosen"]
    M_ = _models()
    rules = {_rname(r): r for r in [V3_RULE] + GRID}
    spec = {f"{chosen}-m0-{k}": (chosen, 0, r) for k, r in rules.items()}
    sim = _sim_summary(_closed_loop(spec, "blocksel"))
    sim["rule"] = sim.key.str.replace(f"{chosen}-m0-", "", regex=False)
    rp = _replay_grid(M_["cands"][(chosen, 0)], M_["taus"][(chosen, 0)]["T1"], rules)
    rp.to_csv(f"{OUT}/blocksel_replay.csv", index=False)
    g = rp.groupby("rule")
    rep = pd.DataFrame({"replay_benign_blocked": g.apply(lambda x: int((x.blocked & (x.label == 0)).sum())),
                        "replay_attack_blocked": g.apply(lambda x: int((x.blocked & (x.label == 1)).sum())),
                        "replay_attack_blocked_A2": g.apply(lambda x: int((x.blocked & (x.label == 1) & (x.variant == "A2")).sum()))})
    t = sim.merge(rep, left_on="rule", right_index=True)
    ref_a2 = float(t[t.rule == "v3rule"].a2_attack_hosts_blocked.iloc[0])
    t["eligible"] = (t.benign_host_blocks == 0) & (t.replay_benign_blocked == 0) & \
                    (t.a2_attack_hosts_blocked >= ref_a2 - 1e-9) & (t.rule != "v3rule")
    ok = t[t.eligible]
    if ok.empty:
        choice = "v3rule"
    else:
        best = ok.attack_occ_pct.min()
        choice = ok[ok.attack_occ_pct <= best + 0.5].sort_values("harm_pct").rule.iloc[0]
    v3_replay = int(t[t.rule == "v3rule"].replay_benign_blocked.iloc[0])
    t.round(3).to_csv(f"{OUT}/blocksel.csv", index=False)
    json.dump(dict(chosen_detector=chosen, chosen_rule=choice, rule=rules[choice],
                   v3_rule_replay_benign_blocked=v3_replay), open(f"{OUT}/blocksel.json", "w"), indent=1)
    L = ["# v4-lite step 3: block-rule floor (docs/v4lite_plan.md)", "",
         f"Detector: {chosen} (model seed 0). Simulator: D1-D3, A2/A4/E9P/A6/benign x seeds 2000-2002 (closed loop). "
         "Replay: the 12 testbed entry logs x s11-s13 (open loop, T1 tau).", "",
         "| Rule | harm % | attack occ % | benign hosts blocked (sim) | attack hosts blocked, A2 (sim, per episode) | "
         "benign hosts blocked (replay) | attack hosts blocked (replay; A2) | eligible |",
         "|---|---|---|---|---|---|---|---|"]
    for _, r in t.sort_values("rule").iterrows():
        L.append(f"| {r.rule} | {r.harm_pct:.3f} | {r.attack_occ_pct:.2f} | {r.benign_host_blocks} | "
                 f"{r.a2_attack_hosts_blocked:.2f} | {r.replay_benign_blocked} | {r.replay_attack_blocked} ({r.replay_attack_blocked_A2}) | "
                 f"{'yes' if r.eligible else 'no'} |")
    L += ["", f"**Chosen: {choice}.**"]
    if v3_replay == 0:
        L.append("The v3 rule blocks no benign host in the replay, so the replay does not reproduce the "
                 "H4 failure (stated as fixed in the plan).")
    open(f"{OUT}/blocksel.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------- step 4
def stage_cache():
    sel = json.load(open(f"{OUT}/blocksel.json"))
    c = sel["chosen_detector"]
    if os.path.exists(f"{OUT}/cache.csv"):
        return _cache_report(pd.read_csv(f"{OUT}/cache.csv"), c)
    M_ = _models()
    model, tau = M_["cands"][(c, 0)], M_["taus"][(c, 0)]["T1"]
    rows = []
    for v, s, d in _replay_runs():
        for sw in ("s11", "s12", "s13"):
            r = _replay(model, tau, sel["rule"], d, sw, cache=True)
            # full-scoring time on the same switch log, for the saving
            sys.path.insert(0, "testbed")
            import entrylog
            from .features import FeatureTracker
            base = os.path.join(d, f"switch_T1_{sw}")
            src, _, _ = entrylog.load_keys(base + "_keys.csv")
            tr = FeatureTracker(len(src), src, 3500, 1.0)
            t_full = 0.0
            for t, fids, pk, by, inst, installs in entrylog.read_entries(base + "_entries.bin"):
                X, _, _ = tr.observe(t, fids, pk, by, inst, installs)
                if len(fids):
                    t0 = time.perf_counter()
                    model.predict_proba(X)
                    t_full += time.perf_counter() - t0
            rows.append(dict(variant=v, seed=s, switch=sw, n=r["n"], agree_pct=100 * r["agree"],
                             t_full_s=t_full, t_cached_s=r["t_cached"]))
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.round(4).to_csv(f"{OUT}/cache.csv", index=False)
    _cache_report(df, c)


def _cache_report(df, c):
    agree = 100 * float((df.agree_pct / 100 * df.n).sum() / df.n.sum())
    saving = 100 * (1 - df.t_cached_s.sum() / df.t_full_s.sum())
    adopt = bool(agree >= 99.9 and saving >= 30)
    json.dump(dict(agree_pct=agree, time_saving_pct=saving, adopt=adopt), open(f"{OUT}/cache.json", "w"), indent=1)
    L = ["# v4-lite step 4: score only changed entries (docs/v4lite_plan.md)", "",
         f"Detector {c}, testbed replay (12 recordings x 3 switches, polls with the table >= rho).", "",
         f"- eviction decisions that agree with full scoring: **{agree:.3f} %** (bar 99.9 %)",
         f"- scoring time saved: **{saving:.1f} %** (bar 30 %)",
         f"- **adopt: {'yes' if adopt else 'no'}**", "", "```", df.round(3).to_string(index=False), "```"]
    open(f"{OUT}/cache.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------- export for the testbed
def stage_export():
    """results/v21/exported/ens_config_v4lite.json for the Ryu app's ensguard-v4lite. The
    CatBoost members are the deployed v3 ones (model seed 0), so their JSON files are reused;
    the controller's JSON scorer must reproduce the simulator's scores."""
    from .ensjson import EnsembleJSON
    exp = "results/v21/exported"
    v3 = json.load(open(f"{exp}/ens_config.json"))
    sel = json.load(open(f"{OUT}/blocksel.json"))
    cache = json.load(open(f"{OUT}/cache.json")) if os.path.exists(f"{OUT}/cache.json") else {"adopt": False}
    c = sel["chosen_detector"]
    M_ = _models()
    r = sel["rule"]
    cfg = dict(selected=f"v4lite-{c}-{_rname(r)}", rf=[] if c == "cb" else v3["rf"], cb=v3["cb"],
               budget=BUDGET, tau={d: M_["taus"][(c, 0)][d] for d in ("D1", "D2", "D3", "T1")},
               rho=v3["rho"], rf_params=v3["rf_params"],
               block=dict(n_min=r["n_min"], k=r["f_min"], block_s=r["block_s"], window_s=10.0,
                          m0=r["m0"], frac_min=r["frac_min"]),
               score_changed_only=bool(cache["adopt"]), fast_cb=True)
    json.dump(cfg, open(f"{exp}/ens_config_v4lite.json", "w"), indent=1)
    chk = np.load(f"{exp}/ens_check.npz")
    err = float(np.abs(EnsembleJSON(exp, cfg).predict_proba(chk["X"]) - M_["cands"][(c, 0)].predict_proba(chk["X"])).max())
    print(json.dumps(cfg, indent=1))
    print(f"controller JSON scorer vs simulator model: max |diff| {err:.2e}")
    assert err < 1e-6, err


if __name__ == "__main__":
    {"models": stage_models, "detsel": stage_detsel, "blocksel": stage_blocksel,
     "cache": stage_cache, "export": stage_export}[sys.argv[1]]()
