import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fl"))
import secagg_xgb as sx  # noqa: E402


def _data(tmp, n=6000, seed=0):
    rng = np.random.default_rng(seed)
    X = (rng.integers(0, 10, (n, 17)) / 10).astype(np.float32)
    y = ((X[:, 0] + 0.5 * X[:, 3] - 0.7 * X[:, 7] + rng.normal(0, 0.15, n)) > 0.4).astype(np.float32)
    for i, part in enumerate(np.array_split(np.arange(n), 3)):
        np.savez(tmp / f"C{i + 1}.npz", X=X[part], y=y[part])
    return X, y


def _run(tmp, masked, trees, name):
    sx.DATA, sx.OUT, sx.TREES, sx.IDLE_S = str(tmp), str(tmp), trees, 0.0
    assert sx.train(masked, 0, name)
    return json.load(open(tmp / f"{name}.json"))


def test_masks_cancel():
    rng = np.random.default_rng(1)
    v = [rng.normal(0, 1e4, 5000) for _ in range(3)]
    exact = sx.decode(sx.encode(v[0]) + sx.encode(v[1]) + sx.encode(v[2]))
    assert np.array_equal(sx.secure_sum(v), exact)
    m = sx.Masker(0)
    assert not np.array_equal(m.mask(sx.encode(v[0]), 0), sx.encode(v[0])) or not m.keys


def test_masked_equals_unmasked(tmp_path):
    X, _ = _data(tmp_path)
    a = _run(tmp_path, True, 5, "m")
    b = _run(tmp_path, False, 5, "u")
    assert a["trees"] == b["trees"] and a["base_margin"] == b["base_margin"]
    assert np.array_equal(sx.predict_margin(a, X), sx.predict_margin(b, X))


def test_matches_xgboost(tmp_path):
    import xgboost as xgb
    X, y = _data(tmp_path, seed=2)
    m = _run(tmp_path, True, 10, "m")
    bst = xgb.train(dict(objective="binary:logistic", eta=0.1, max_depth=6, tree_method="hist", max_bin=256,
                         nthread=1, seed=0), xgb.DMatrix(X, label=y), num_boost_round=10)
    first = bst.get_dump(dump_format="json")[0]
    assert json.loads(first)["split"] == f"f{m['trees'][0]['feature'][0]}"
    assert np.abs(sx.predict_proba(m, X) - bst.predict(xgb.DMatrix(X))).max() < 1e-4
