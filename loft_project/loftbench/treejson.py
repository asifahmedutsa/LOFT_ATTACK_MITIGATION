"""Evaluate exported XGBoost and scikit-learn forest classifiers with NumPy only.

The Ryu testbed runs on Python 3.8 without XGBoost; FTMaster's XGBoost and FTOP's Random
Forest models are exported here to one JSON format (flat node arrays per tree) and evaluated
by TreeJSON. Both libraries compare float32 features, so the evaluator does too.

    export(model, path, X_check)   # writes the JSON and asserts parity on X_check
"""
import json

import numpy as np


class TreeJSON:
    """kind "xgb": P(1) = sigmoid(base_margin + sum of leaves), split goes left when x < thr.
    kind "rf": P = mean over trees of the leaf class fractions, split goes left when x <= thr."""

    def __init__(self, path_or_dict):
        m = path_or_dict if isinstance(path_or_dict, dict) else json.load(open(path_or_dict))
        self.kind = m["kind"]
        self.base = float(m.get("base_margin", 0.0))
        feat, thr, left, right, val, roots, off = [], [], [], [], [], [], 0
        for t in m["trees"]:
            n = len(t["feature"])
            roots.append(off)
            feat.append(np.asarray(t["feature"], int))
            thr.append(np.asarray(t["threshold"], float))
            lc, rc = np.asarray(t["left"], int), np.asarray(t["right"], int)
            left.append(np.where(lc >= 0, lc + off, -1))
            right.append(np.where(rc >= 0, rc + off, -1))
            val.append(np.asarray(t["value"], float))
            off += n
        self.feat, self.thr = np.concatenate(feat), np.concatenate(thr)
        self.left, self.right = np.concatenate(left), np.concatenate(right)
        self.val, self.roots = np.concatenate(val), np.asarray(roots, int)
        if self.kind == "xgb":
            self.thr = self.thr.astype(np.float32)

    def _leaves(self, X):
        X = np.asarray(X, np.float32)
        n, k = len(X), len(self.roots)
        node = np.tile(self.roots, n)                 # (row, tree) pairs, row-major
        row = np.repeat(np.arange(n), k)
        act = np.flatnonzero(self.left[node] >= 0)    # pairs still at an inner node
        while len(act):
            nd = node[act]
            x = X[row[act], self.feat[nd]]
            go = (x < self.thr[nd]) if self.kind == "xgb" else (x.astype(float) <= self.thr[nd])
            nd = np.where(go, self.left[nd], self.right[nd])
            node[act] = nd
            act = act[self.left[nd] >= 0]
        return node.reshape(n, k)

    def predict_proba(self, X):
        if len(X) == 0:
            return np.zeros((0, 2))
        v = self.val[self._leaves(X)]
        if self.kind == "xgb":
            p = 1.0 / (1.0 + np.exp(-(self.base + v.sum(1))))
        else:
            p = v.mean(1)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _xgb_dict(model, X_check):
    js = json.loads(model.get_booster().save_raw("json").decode())
    trees = []
    for t in js["learner"]["gradient_booster"]["model"]["trees"]:
        lc = np.asarray(t["left_children"], int)
        cond = np.asarray(t["split_conditions"], float)
        trees.append(dict(feature=t["split_indices"], threshold=cond.tolist(), left=lc.tolist(),
                          right=t["right_children"],
                          value=np.where(lc < 0, cond, 0.0).tolist()))
    d = dict(kind="xgb", base_margin=0.0, trees=trees)
    leaves = TreeJSON(d).predict_proba(X_check[:50])
    s = np.log(leaves[:, 1] / leaves[:, 0])
    d["base_margin"] = float(np.median(model.predict(X_check[:50], output_margin=True) - s))
    return d


def _rf_dict(model):
    trees = []
    for e in model.estimators_:
        t = e.tree_
        v = t.value[:, 0, :]
        frac = v / np.maximum(v.sum(1, keepdims=True), 1e-12)
        trees.append(dict(feature=t.feature.tolist(), threshold=t.threshold.tolist(),
                          left=t.children_left.tolist(), right=t.children_right.tolist(),
                          value=frac[:, list(model.classes_).index(1)].tolist()))
    return dict(kind="rf", trees=trees)


def export(model, path, X_check):
    """Write `model` (XGBClassifier or RandomForestClassifier) and check parity on X_check."""
    X_check = np.asarray(X_check, np.float32)
    d = _xgb_dict(model, X_check) if type(model).__module__.startswith("xgboost") else _rf_dict(model)
    with open(path, "w") as f:
        json.dump(d, f)
    got = TreeJSON(path).predict_proba(X_check)[:, 1]
    want = model.predict_proba(X_check)[:, 1]
    err = float(np.abs(got - want).max())
    assert err < 1e-4, f"{path}: parity error {err}"
    return err
