"""Evaluate CatBoost models exported with save_model(format="json"), NumPy only.

The Ryu testbed runs on Python 3.8 without CatBoost; DMS-BTT's state and flow classifiers
are exported to JSON and evaluated here. Only numeric features are supported (DMS-BTT
uses FN, APIT and Numb, PIT, Sizep). Parity with CatBoost is checked by
tests/test_loftbench.py and by `python -m loftbench.cbjson --check`.
"""
import json

import numpy as np


class CatBoostJSON:
    def __init__(self, path_or_dict):
        m = path_or_dict if isinstance(path_or_dict, dict) else json.load(open(path_or_dict))
        trees = m["oblivious_trees"]
        sb = m.get("scale_and_bias", [1.0, [0.0]])
        self.scale = float(sb[0])
        self.bias = np.atleast_1d(np.asarray(sb[1], float))
        self.feat, self.border, self.leaves, self.depth = [], [], [], []
        for t in trees:
            sp = t.get("splits") or []
            self.feat.append(np.array([s["float_feature_index"] for s in sp], int))
            self.border.append(np.array([s["border"] for s in sp], float))
            self.depth.append(len(sp))
            self.leaves.append(np.asarray(t["leaf_values"], float))
        n_leaf = 2 ** self.depth[0] if self.depth else 1
        self.dim = max(1, len(self.leaves[0]) // n_leaf) if self.leaves else len(self.bias)

    def raw(self, X):
        X = np.asarray(X, float)
        out = np.zeros((len(X), self.dim))
        for f, b, lv, d in zip(self.feat, self.border, self.leaves, self.depth):
            idx = np.zeros(len(X), int)
            for j in range(d):
                idx |= (X[:, f[j]] > b[j]).astype(int) << j
            out += lv.reshape(2 ** d, self.dim)[idx]
        return self.scale * out + self.bias

    def predict_proba(self, X):
        r = self.raw(X)
        if self.dim == 1:
            p = 1.0 / (1.0 + np.exp(-r[:, 0]))
            return np.column_stack([1 - p, p])
        e = np.exp(r - r.max(axis=1, keepdims=True))
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, X):
        r = self.raw(X)
        if self.dim == 1:
            return (r[:, 0] > 0).astype(int)
        return r.argmax(axis=1)


def export(catboost_model, path):
    catboost_model.save_model(path, format="json")


def _check():
    """Parity of the exported revision-2 DMS-BTT models with CatBoost on validation rows."""
    import os
    import pickle
    import tempfile
    m, _ = pickle.load(open("results/revision2/models.pkl", "rb"))
    data = pickle.load(open("results/v2/datasets.pkl", "rb"))
    for d in ("D1", "D2", "D3"):
        va = data[("val", d)]
        for key, X in ((f"state/{d}", va.state[:, :2]), (f"flow/bytes/{d}", va.dms)):
            cb = m[key].m
            with tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, "m.json")
                export(cb, p)
                mine = CatBoostJSON(p)
            a = cb.predict_proba(X, thread_count=1)
            b = mine.predict_proba(X)
            same = np.mean(np.ravel(cb.predict(X, thread_count=1)).astype(int) == mine.predict(X))
            print(f"{key:14s} rows {len(X):6d}  max |p diff| {np.abs(a - b).max():.2e}  same label {same:.4f}")


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        _check()
