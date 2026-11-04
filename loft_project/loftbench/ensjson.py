"""The federated RF + CatBoost ensemble of loftbench.evictblock, exported for the Ryu testbed
(Python 3.8, NumPy only).

Each controller D1-D3 contributes its local Random Forest (50 trees, depth 12) and CatBoost
model (model sharing); the score is the mean of the forests' mean and the boosters' mean, as
M.Mean([M.Mean(rf), M.Mean(cb)]) in the simulator. ens_config.json holds the member files, tau
per domain (0.1 % benign budget on that domain's validation data; T1 on the bigFlows trace's
validation runs of revision 5) and the selected block rule.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.ensjson   # writes results/v21/exported/
    # then, with the testbed's Python (scikit-learn 1.3.2), the fast forests:
    ~/ryu-env/bin/python3.8 -c "import sys; sys.path.insert(0, '.'); from loftbench.ensjson import \
        build_sklearn_forests as b; b('results/v21/exported', 'results/e3_ens/train')"
"""
import json
import os

import numpy as np

from .cbjson import CatBoostJSON
from .treejson import TreeJSON


class FastForest:
    """TreeJSON's random forest evaluated level by level over a dense (row, tree) grid: the
    same leaves (rows go left when x <= threshold), about 10x faster for 50 deep trees."""

    def __init__(self, tj):
        self.t = tj
        self.depth = self._depth()
        # Leaves get feature -1, so one lookup tells inner nodes from leaves.
        self.feat = np.where(tj.left >= 0, tj.feat, -1).astype(np.int32)
        self.thr, self.val = tj.thr, tj.val
        self.left, self.right = tj.left.astype(np.int32), tj.right.astype(np.int32)

    def _depth(self):
        t, best = self.t, 0
        for r in t.roots:
            stack = [(r, 0)]
            while stack:
                nd, dd = stack.pop()
                if t.left[nd] < 0:
                    best = max(best, dd)
                else:
                    stack += [(t.left[nd], dd + 1), (t.right[nd], dd + 1)]
        return best

    def predict_proba(self, X):
        t = self.t
        X = np.ascontiguousarray(X, float)
        n, nf = X.shape
        flat = X.ravel()
        base = (np.arange(n) * nf)[:, None]
        node = np.tile(t.roots, (n, 1))
        for _ in range(self.depth):
            f = self.feat[node]
            inner = f >= 0
            if not inner.any():
                break
            x = flat[base + np.maximum(f, 0)]
            nxt = np.where(x <= self.thr[node], self.left[node], self.right[node])
            node = np.where(inner, nxt, node)
        p = self.val[node].mean(1)
        return np.column_stack([1 - p, p])


class FastOblivious:
    """CatBoostJSON with every tree of one model evaluated at once (all trees have the same
    depth in an oblivious model); the same leaves (bit j set when x > border). Each feature is
    first mapped to the number of the model's borders below it, so the per-tree test is an
    integer comparison (x > border r  <=>  #borders below x > r)."""

    def __init__(self, cj, chunk=1000):
        assert len(set(cj.depth)) == 1 and cj.dim == 1, "fast path needs equal depth, binary"
        self.c, self.chunk = cj, chunk
        F = np.array(cj.feat, int)                      # (trees, depth)
        B = np.array(cj.border, float)
        self.feats = sorted(set(F.ravel().tolist()))
        self.borders = {f: np.unique(B[F == f]) for f in self.feats}
        col = {f: i for i, f in enumerate(self.feats)}
        self.Fc = np.vectorize(col.get)(F).astype(np.int32)
        self.R = np.vectorize(lambda f, b: int(np.searchsorted(self.borders[f], b)))(F, B).astype(np.int16)
        self.L = np.array(cj.leaves, float)             # (trees, 2^depth)
        self.Lflat = self.L.ravel()
        self.ar = np.arange(len(F))

    def predict_proba(self, X):
        X = np.asarray(X, float)
        cnt = np.column_stack([np.searchsorted(self.borders[f], X[:, f], side="left")
                               for f in self.feats]).astype(np.int16)
        n_leaf = self.L.shape[1]
        idx = np.zeros((len(X), len(self.ar)), np.int32)
        for j in range(self.Fc.shape[1]):              # one depth level for all trees at once
            idx |= (cnt[:, self.Fc[:, j]] > self.R[:, j]).astype(np.int32) << j
        raw = self.Lflat[idx + self.ar * n_leaf].sum(1)
        r = self.c.scale * raw + self.c.bias[0]
        p = 1.0 / (1.0 + np.exp(-r))
        return np.column_stack([1 - p, p])


class EnsembleJSON:
    """The forests come from scikit-learn pickles (ens_rf_<D>.pkl, built by
    build_sklearn_forests in the testbed's own Python, 3-8x faster than NumPy) when they load
    and reproduce ens_check.npz exactly; otherwise from the JSON files."""

    def __init__(self, model_dir, cfg=None):
        cfg = cfg or json.load(open(os.path.join(model_dir, "ens_config.json")))
        self.cb = [FastOblivious(CatBoostJSON(os.path.join(model_dir, f))) for f in cfg["cb"]]
        self.rf = [FastForest(TreeJSON(os.path.join(model_dir, f))) for f in cfg["rf"]]
        self.rf_source = "json"
        try:
            import pickle
            sk = [pickle.load(open(os.path.join(model_dir, f.replace(".json", ".pkl")), "rb"))
                  for f in cfg["rf"]]
            chk = np.load(os.path.join(model_dir, "ens_check.npz"))
            got = np.column_stack([m.predict_proba(chk["X"])[:, 1] for m in sk])
            if np.abs(got - chk["rf"]).max() < 1e-9:
                self.rf, self.rf_source = sk, "sklearn"
        except Exception:
            pass

    def predict_proba(self, X):
        if len(X) == 0:
            return np.zeros(0)
        rf = np.mean([m.predict_proba(X)[:, 1] for m in self.rf], axis=0)
        cb = np.mean([m.predict_proba(X)[:, 1] for m in self.cb], axis=0)
        return (rf + cb) / 2


def build_sklearn_forests(model_dir, train_dir):
    """Run with the testbed's Python: refit each controller's forest with the same settings
    and seed from the exported training arrays and keep it only if it reproduces the
    simulator's forest exactly on ens_check.npz."""
    import pickle

    from sklearn.ensemble import RandomForestClassifier
    cfg = json.load(open(os.path.join(model_dir, "ens_config.json")))
    chk = np.load(os.path.join(model_dir, "ens_check.npz"))
    for i, f in enumerate(cfg["rf"]):
        d = f[len("ens_rf_"):-len(".json")]
        tr = np.load(os.path.join(train_dir, f"train_{d}.npz"))
        m = RandomForestClassifier(n_jobs=4, random_state=0, **cfg["rf_params"]).fit(tr["X"], tr["y"])
        m.n_jobs = 1
        err = float(np.abs(m.predict_proba(chk["X"])[:, 1] - chk["rf"][:, i]).max())
        print(f"  {d}: refit forest vs simulator, max diff {err}")
        assert err < 1e-9, f"{d}: forest differs ({err}); the controller keeps the JSON forest"
        pickle.dump(m, open(os.path.join(model_dir, f.replace(".json", ".pkl")), "wb"))


def main():
    import pickle

    from . import flowhold as FH
    from . import revision5 as R5
    from .cbjson import export as cb_export
    from .evictblock import BUDGETS, _parse
    from .models import threshold_at_fpr
    from .treejson import export as rf_export

    out = "results/v21/exported"
    sel = json.load(open("results/evictblock/selected.json"))["selected"]["ens"]
    _, budget, (n_min, k), block_s = _parse(sel)
    assert budget in BUDGETS
    ens = pickle.load(open("results/e3_ens/models.pkl", "rb"))["ens"]
    rf_fed, cb_fed = ens.ms
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    Xc = data[("val", "D1")].X[:4000]
    from .e1_pair import RF
    cfg = dict(selected=sel, rf=[], cb=[], budget=budget, tau={}, rho={}, rf_params=RF["rf50d12"],
               block=dict(n_min=n_min, k=k, block_s=block_s, window_s=10.0))
    for i, d in enumerate(("D1", "D2", "D3")):
        f_rf, f_cb = f"ens_rf_{d}.json", f"ens_cb_{d}.json"
        err = rf_export(rf_fed.ms[i].m, os.path.join(out, f_rf), Xc)
        cb_export(cb_fed.ms[i].m, os.path.join(out, f_cb))
        cfg["rf"].append(f_rf)
        cfg["cb"].append(f_cb)
        print(f"  {d}: RF parity {err:.1e}", flush=True)
    os.makedirs("results/e3_ens/train", exist_ok=True)
    for d in ("D1", "D2", "D3"):
        np.savez(f"results/e3_ens/train/train_{d}.npz", X=data[("train", d)].X, y=data[("train", d)].y)
    np.savez(os.path.join(out, "ens_check.npz"), X=Xc,
             rf=np.column_stack([m.predict_proba(Xc) for m in rf_fed.ms]))
    E = EnsembleJSON(out, cfg)
    err = float(np.abs(E.predict_proba(Xc) - ens.predict_proba(Xc)).max())
    print(f"  ensemble parity {err:.1e}")
    assert err < 1e-4, err
    FH._load()
    for d in ("D1", "D2", "D3"):
        v = data[("val", d)]
        cfg["tau"][d] = threshold_at_fpr(E.predict_proba(v.X[v.y == 0]), budget)
        cfg["rho"][d] = FH._dg(d).rho
    runs = pickle.load(open("results/revision5/trace_runs.pkl", "rb"))
    for t in ("T1", "T2"):
        ben = np.concatenate([runs[(t, None, s)].X[runs[(t, None, s)].y == 0] for s in (2000, 2001, 2002)])
        cfg["tau"][t] = threshold_at_fpr(E.predict_proba(ben), budget)
        cfg["rho"][t] = R5.make("v2.1", t).rho
    json.dump(cfg, open(os.path.join(out, "ens_config.json"), "w"), indent=1)
    print(json.dumps({k: cfg[k] for k in ("selected", "tau", "rho", "block")}, indent=1))


if __name__ == "__main__":
    main()
