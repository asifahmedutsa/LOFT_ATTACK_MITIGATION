"""The federated RF + CatBoost ensemble of loftbench.evictblock, exported for the Ryu testbed
(Python 3.8, NumPy only).

Each controller D1-D3 contributes its local Random Forest (50 trees, depth 12) and CatBoost
model (model sharing); the score is the mean of the forests' mean and the boosters' mean, as
M.Mean([M.Mean(rf), M.Mean(cb)]) in the simulator. ens_config.json holds the member files, tau
per domain (0.1 % benign budget on that domain's validation data; T1 on the bigFlows trace's
validation runs of revision 5) and the selected block rule.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.ensjson   # writes results/v21/exported/
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
        X = np.asarray(X, float)
        node = np.tile(t.roots, (len(X), 1))
        feat = np.maximum(t.feat, 0)
        for _ in range(self.depth):
            inner = t.left[node] >= 0
            if not inner.any():
                break
            x = np.take_along_axis(X, feat[node], axis=1)
            nxt = np.where(x <= t.thr[node], t.left[node], t.right[node])
            node = np.where(inner, nxt, node)
        p = t.val[node].mean(1)
        return np.column_stack([1 - p, p])


class FastOblivious:
    """CatBoostJSON with every tree of one model evaluated at once (all trees have the same
    depth in an oblivious model); the same leaves (bit j set when x > border)."""

    def __init__(self, cj, chunk=2000):
        assert len(set(cj.depth)) == 1 and cj.dim == 1, "fast path needs equal depth, binary"
        self.c, self.chunk = cj, chunk
        self.F = np.array(cj.feat, int)                 # (trees, depth)
        self.B = np.array(cj.border, float)
        self.L = np.array(cj.leaves, float)             # (trees, 2^depth)
        self.w = 1 << np.arange(self.F.shape[1])

    def predict_proba(self, X):
        X = np.asarray(X, float)
        raw = np.empty(len(X))
        ar = np.arange(len(self.F))
        for i in range(0, len(X), self.chunk):
            xs = X[i:i + self.chunk][:, self.F]          # (rows, trees, depth)
            idx = ((xs > self.B) * self.w).sum(-1)
            raw[i:i + self.chunk] = self.L[ar, idx].sum(1)
        r = self.c.scale * raw + self.c.bias[0]
        p = 1.0 / (1.0 + np.exp(-r))
        return np.column_stack([1 - p, p])


class EnsembleJSON:
    def __init__(self, model_dir, cfg=None):
        cfg = cfg or json.load(open(os.path.join(model_dir, "ens_config.json")))
        self.rf = [FastForest(TreeJSON(os.path.join(model_dir, f))) for f in cfg["rf"]]
        self.cb = [FastOblivious(CatBoostJSON(os.path.join(model_dir, f))) for f in cfg["cb"]]

    def predict_proba(self, X):
        if len(X) == 0:
            return np.zeros(0)
        rf = np.mean([m.predict_proba(X)[:, 1] for m in self.rf], axis=0)
        cb = np.mean([m.predict_proba(X)[:, 1] for m in self.cb], axis=0)
        return (rf + cb) / 2


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
    cfg = dict(selected=sel, rf=[], cb=[], budget=budget, tau={}, rho={},
               block=dict(n_min=n_min, k=k, block_s=block_s, window_s=10.0))
    for i, d in enumerate(("D1", "D2", "D3")):
        f_rf, f_cb = f"ens_rf_{d}.json", f"ens_cb_{d}.json"
        err = rf_export(rf_fed.ms[i].m, os.path.join(out, f_rf), Xc)
        cb_export(cb_fed.ms[i].m, os.path.join(out, f_cb))
        cfg["rf"].append(f_rf)
        cfg["cb"].append(f_cb)
        print(f"  {d}: RF parity {err:.1e}", flush=True)
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
