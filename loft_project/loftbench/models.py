"""Detectors and federated learning.

The shared backbone is a small MLP implemented in NumPy so that its weights
can be exchanged exactly (FedAvg / FedProx). Every client applies the received
global weights before local training and before inference; the server only
sees weights and normalization sufficient statistics, never flow records.
"""
import numpy as np


class Standardizer:
    def __init__(self, mean, std):
        self.mean = mean.astype(np.float32)
        self.std = np.maximum(std, 1e-6).astype(np.float32)

    @classmethod
    def fit(cls, X):
        return cls(X.mean(0), X.std(0))

    @classmethod
    def from_stats(cls, stats):
        """Combine per-client (n, sum, sumsq) without sharing records."""
        n = sum(s[0] for s in stats)
        s1 = sum(s[1] for s in stats)
        s2 = sum(s[2] for s in stats)
        mean = s1 / n
        return cls(mean, np.sqrt(np.maximum(s2 / n - mean ** 2, 0)))

    @staticmethod
    def stats(X):
        X = X.astype(np.float64)
        return len(X), X.sum(0), (X ** 2).sum(0)

    def __call__(self, X):
        return (X - self.mean) / self.std


class MLP:
    """d -> h -> 1 ReLU network, weighted binary cross-entropy, Adam."""

    def __init__(self, d, hidden=32, seed=0):
        r = np.random.default_rng(seed)
        self.params = [
            (r.standard_normal((d, hidden)) * np.sqrt(2 / d)).astype(np.float32),
            np.zeros(hidden, np.float32),
            (r.standard_normal((hidden, 1)) * np.sqrt(1 / hidden)).astype(np.float32),
            np.zeros(1, np.float32),
        ]
        self.scaler = None

    # --- weights exchange -------------------------------------------------
    def get_weights(self):
        return [p.copy() for p in self.params]

    def set_weights(self, ws):
        self.params = [w.astype(np.float32).copy() for w in ws]

    def n_bytes(self):
        return int(sum(p.size for p in self.params) * 4)

    # --- model -------------------------------------------------------------
    def _forward(self, X):
        W1, b1, W2, b2 = self.params
        H = np.maximum(X @ W1 + b1, 0)
        z = (H @ W2 + b2)[:, 0]
        return H, z

    def predict_proba(self, X):
        Xs = self.scaler(X) if self.scaler is not None else X
        _, z = self._forward(Xs.astype(np.float32))
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    def fit(self, X, y, epochs=1, lr=3e-3, batch=512, seed=0, prox_ref=None, mu=0.0,
            pos_weight=None):
        r = np.random.default_rng(seed)
        Xs = self.scaler(X).astype(np.float32) if self.scaler is not None else X
        y = y.astype(np.float32)
        if pos_weight is None:
            npos = max(y.sum(), 1)
            pos_weight = float(np.clip((len(y) - npos) / npos, 1, 20))
        m = [np.zeros_like(p) for p in self.params]
        v = [np.zeros_like(p) for p in self.params]
        step = 0
        for _ in range(epochs):
            idx = r.permutation(len(y))
            for s in range(0, len(y), batch):
                b = idx[s:s + batch]
                xb, yb = Xs[b], y[b]
                H, z = self._forward(xb)
                p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
                w = np.where(yb > 0, pos_weight, 1.0)
                g = (w * (p - yb) / w.sum())[:, None]
                W1, b1, W2, b2 = self.params
                gW2 = H.T @ g
                gb2 = g.sum(0)
                gH = g @ W2.T * (H > 0)
                gW1 = xb.T @ gH
                gb1 = gH.sum(0)
                grads = [gW1, gb1, gW2, gb2]
                if prox_ref is not None and mu > 0:
                    grads = [gr + mu * (pa - pr) for gr, pa, pr in zip(grads, self.params, prox_ref)]
                step += 1
                for i, gr in enumerate(grads):
                    m[i] = 0.9 * m[i] + 0.1 * gr
                    v[i] = 0.999 * v[i] + 0.001 * gr * gr
                    mh = m[i] / (1 - 0.9 ** step)
                    vh = v[i] / (1 - 0.999 ** step)
                    self.params[i] -= (lr * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32)
        return self


def train_local(X, y, epochs=30, seed=0, hidden=32):
    model = MLP(X.shape[1], hidden, seed)
    model.scaler = Standardizer.fit(X)
    model.fit(X, y, epochs=epochs, seed=seed)
    return model


def train_federated(client_data, rounds=30, local_epochs=1, mu=0.0, seed=0, hidden=32,
                    log=None, weights=None):
    """FedAvg (mu=0) or FedProx (mu>0) over clients [(X, y), ...].

    Updates are averaged with weights proportional to the clients' row counts, or to
    `weights` when given (one per client).

    Returns the global model and a communication/convergence log.
    """
    d = client_data[0][0].shape[1]
    glob = MLP(d, hidden, seed)
    # Round 0: federated normalization from sufficient statistics.
    glob.scaler = Standardizer.from_stats([Standardizer.stats(X) for X, _ in client_data])
    stats_bytes = len(client_data) * (1 + 2 * d) * 8
    n = np.array([len(y) for _, y in client_data] if weights is None else weights, float)
    history = []
    up_bytes = down_bytes = 0
    for r in range(rounds):
        gw = glob.get_weights()
        updates = []
        for c, (X, y) in enumerate(client_data):
            local = MLP(d, hidden)
            local.scaler = glob.scaler
            local.set_weights(gw)                       # apply received global weights
            down_bytes += glob.n_bytes()
            local.fit(X, y, epochs=local_epochs, seed=seed * 1000 + r * 10 + c,
                      prox_ref=gw if mu > 0 else None, mu=mu)
            updates.append(local.get_weights())
            up_bytes += local.n_bytes()
        agg = [sum(w * u[i] for w, u in zip(n / n.sum(), updates)) for i in range(len(gw))]
        glob.set_weights(agg)
        if log is not None:
            history.append(log(r, glob))
    comm = dict(rounds=rounds, model_bytes=glob.n_bytes(), uplink_bytes=up_bytes,
                downlink_bytes=down_bytes, normalization_bytes=stats_bytes,
                total_bytes=up_bytes + down_bytes + stats_bytes)
    return glob, comm, history


def threshold_at_fpr(scores_benign, fpr):
    """Smallest threshold whose empirical benign flag rate is <= fpr."""
    s = np.sort(scores_benign)
    k = int(np.ceil((1 - fpr) * len(s))) - 1
    return float(s[min(max(k, 0), len(s) - 1)]) + 1e-9


# Picklable wrappers giving every detector a predict_proba(X) -> P(attack).
class CatWrap:
    """CatBoost wrapper that predicts single-threaded inside worker processes."""

    def __init__(self, m):
        self.m = m

    def predict(self, X):
        return self.m.predict(X, thread_count=1)

    def predict_proba(self, X):
        return self.m.predict_proba(X, thread_count=1)


class SubsetModel:
    def __init__(self, m, idx):
        self.m, self.idx = m, idx

    def predict_proba(self, X):
        return self.m.predict_proba(X[:, self.idx])


class SkWrap:
    def __init__(self, m):
        self.m = m

    def predict_proba(self, X):
        return self.m.predict_proba(X)[:, 1]


class _DMSFlowAdapter:
    def __init__(self, m):
        self.m = m

    def predict_proba(self, X):
        return self.m.predict_proba(X)[:, 1]


class DMSFeatureMLP:
    """MLP over DMS-BTT's (Numb, PIT, Sizep) features, for federating DMS-BTT's
    flow classifier (CatBoost cannot be averaged)."""

    def __init__(self, m):
        self.m = m

    @staticmethod
    def features(X):
        return np.column_stack([np.log1p(X[:, 0]), np.log1p(X[:, 1]), X[:, 2] / 1500.0]).astype(np.float32)

    def predict_proba(self, X):
        return self.m.predict_proba(self.features(X))


class EnsembleModel:
    """Average of other controllers' trained models: one-shot model sharing,
    no training rounds (collaboration baseline cheaper than federation)."""

    def __init__(self, members):
        self.members = members

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)
