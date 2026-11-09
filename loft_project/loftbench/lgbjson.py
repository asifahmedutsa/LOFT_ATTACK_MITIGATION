"""LightGBM-LR (FTODefender's rule classifier) in plain NumPy for the testbed controller: the
LightGBM trees map a rule to one leaf per tree, the leaves are one-hot encoded and a logistic
regression gives the attack probability. export() writes the model as JSON; LGBMLRJSON reads it
and reproduces the scikit-learn / LightGBM pipeline exactly (checked on export).
"""
import json

import numpy as np


def _flatten(tree):
    """LightGBM tree_structure -> parallel arrays (feature, threshold, left, right, leaf)."""
    feat, thr, left, right, leaf = [], [], [], [], []

    def add(node):
        i = len(feat)
        feat.append(-1)
        thr.append(0.0)
        left.append(-1)
        right.append(-1)
        leaf.append(-1)
        if "leaf_index" in node:
            leaf[i] = node["leaf_index"]
            return i
        if node.get("decision_type", "<=") != "<=":
            raise ValueError("only numerical <= splits are supported")
        feat[i], thr[i] = node["split_feature"], float(node["threshold"])
        left[i] = add(node["left_child"])
        right[i] = add(node["right_child"])
        return i

    add(tree["tree_structure"])
    return dict(feature=feat, threshold=thr, left=left, right=right, leaf=leaf)


def leaves(booster, X):
    """Leaf index per tree, as LightGBM's predict(pred_leaf=True)."""
    return booster.predict(X, pred_leaf=True).astype(np.int64)


def export(lgbm, lr, path, X_check):
    """lgbm: a fitted lightgbm.LGBMClassifier; lr: a fitted LogisticRegression on the one-hot
    leaves (n_trees x leaves_per_tree columns, column = tree * width + leaf)."""
    dump = lgbm.booster_.dump_model()
    trees = [_flatten(t) for t in dump["tree_info"]]
    width = int(max(t["num_leaves"] for t in dump["tree_info"]))
    js = dict(trees=trees, width=width, coef=lr.coef_.ravel().tolist(), intercept=float(lr.intercept_[0]))
    json.dump(js, open(path, "w"))
    ref = lr.predict_proba(onehot(leaves(lgbm.booster_, X_check), width))[:, 1]
    got = LGBMLRJSON(path).predict_proba(X_check)[:, 1]
    return float(np.abs(ref - got).max())


def onehot(L, width):
    from scipy.sparse import csr_matrix
    # Built as CSR directly (one entry per tree in each row, int32 indices): the same matrix as the
    # COO form, without its int64 row and column arrays (about 3 GB on 1.2 M rows).
    n, t = L.shape
    cols = (np.arange(t, dtype=np.int32)[None, :] * width + L.astype(np.int32)).ravel()
    return csr_matrix((np.ones(n * t), cols, np.arange(0, n * t + 1, t, dtype=np.int64)), shape=(n, t * width))


class LGBMLRJSON:
    def __init__(self, path):
        js = json.load(open(path))
        self.width = js["width"]
        self.coef = np.asarray(js["coef"])
        self.b = js["intercept"]
        self.trees = [{k: np.asarray(v) for k, v in t.items()} for t in js["trees"]]

    def _leaf(self, t, X):
        node = np.zeros(len(X), np.int64)
        while True:
            f = t["feature"][node]
            inner = f >= 0
            if not inner.any():
                return t["leaf"][node]
            idx = np.flatnonzero(inner)
            go_left = X[idx, f[idx]] <= t["threshold"][node[idx]]
            node[idx] = np.where(go_left, t["left"][node[idx]], t["right"][node[idx]])

    def predict_proba(self, X):
        X = np.asarray(X, float)
        z = np.full(len(X), self.b)
        for i, t in enumerate(self.trees):
            z += self.coef[i * self.width + self._leaf(t, X)]
        p = 1.0 / (1.0 + np.exp(-z))
        return np.column_stack([1 - p, p])
