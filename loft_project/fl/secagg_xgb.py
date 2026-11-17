"""Lossless federated XGBoost with secure aggregation of the histograms (docs/secagg_plan.md, section 2).

A small histogram gradient-boosting trainer with FEVER's settings (binary logistic loss, 300 trees,
depth 6, eta 0.1, lambda 1, min_child_weight 1, gamma 0, 256 bins), in which every message between
the controllers is explicit. Three worker processes (C1, C2, C3), each loading only its own rows, and
an aggregator, on loopback. Each worker sends the aggregator only masked vectors:

- bins: its counts on a fixed public grid per feature (4,096 cells over the feature's range); every
  worker takes the same 256 quantile cuts from the sum;
- base score: its label sum and row count;
- trees: for every level, its gradient and hessian sums per node, feature and bin; every worker
  chooses the same splits and leaf values from the sum.

Masking (Bonawitz et al., CCS 2017, without dropout recovery): sums in fixed point (scale 2^40, modulo
2^64); each pair of workers agrees on a key by X25519 and adds a ChaCha20 mask keyed by the pair key
and the message number, with the sign set by the pair's order, so the masks cancel in the sum.

    PYTHONPATH=. ~/.venvs/loft/bin/python fl/secagg_xgb.py                # masked: <OUT>/secagg_masked.json, _log.json
    PYTHONPATH=. ~/.venvs/loft/bin/python fl/secagg_xgb.py --unmasked     # control: masks set to zero
    PYTHONPATH=. ~/.venvs/loft/bin/python fl/secagg_xgb.py --seed 1       # rerun (fresh keys; the trainer draws no
                                                                          # other random numbers)

SECAGG_DATA and SECAGG_OUT choose the controllers' data (default results/tbfl/fl_data) and the output
folder (default results/secagg); SECAGG_TREES the number of trees.
"""
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

DATA = os.environ.get("SECAGG_DATA", "results/tbfl/fl_data")
OUT = os.environ.get("SECAGG_OUT", "results/secagg")
CLIENTS = ("C1", "C2", "C3")
TREES = int(os.environ.get("SECAGG_TREES", "300"))
IDLE_S = float(os.environ.get("SECAGG_IDLE", "10"))   # loopback idle measurement before training
PARAMS = dict(eta=0.1, max_depth=6, reg_lambda=1.0, min_child_weight=1.0, max_bin=256)
RT_EPS = 1e-6                     # smallest gain that splits (XGBoost's kRtEps; gamma 0)
SCALE = 2.0 ** 40                 # fixed point
CELLS = 4096                      # public grid per feature
# Public range per feature, from the definitions in loftbench/features.py (not from the data): log1p
# of counts, bytes and times, fractions in [0, 1], and the coefficient of variation and mean gap.
# Values outside a range fall into its first or last cell.
GRID = [(0, 24), (0, 32), (0, 16), (0, 1), (0, 24), (0, 16), (0, 24), (0, 1), (0, 1), (0, 8), (0, 8),
        (0, 12), (0, 12), (0, 1), (0, 1), (0, 8), (0, 16)]
AUTH = b"fever-secagg"


# ---- fixed point and masks ----

def encode(a):
    return np.round(np.asarray(a, np.float64) * SCALE).astype(np.int64).view(np.uint64)


def decode(u):
    return np.asarray(u, np.uint64).view(np.int64).astype(np.float64) / SCALE


def prg(key, msg, n):
    """n 64-bit words of ChaCha20 keystream for one pair key and message number."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    nonce = (0).to_bytes(4, "little") + int(msg).to_bytes(12, "little")
    enc = Cipher(algorithms.ChaCha20(key, nonce), mode=None).encryptor()
    return np.frombuffer(enc.update(bytes(8 * n)), np.uint64)


class Masker:
    """One controller's pairwise masks: X25519 key agreement, ChaCha20 masks per message."""

    def __init__(self, rank):
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        self.rank, self.sk = rank, X25519PrivateKey.generate()
        self.public = self.sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.keys = {}

    def agree(self, publics):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        for j, pb in enumerate(publics):
            if j != self.rank:
                shared = self.sk.exchange(X25519PublicKey.from_public_bytes(pb))
                self.keys[j] = HKDF(hashes.SHA256(), 32, salt=None, info=b"fever-secagg pair").derive(shared)

    def mask(self, u, msg):
        out = u.copy()
        for j, k in self.keys.items():
            m = prg(k, msg, len(u))
            out = out + m if self.rank < j else out - m      # uint64: wraps modulo 2^64
        return out


def secure_sum(vectors):
    """The masked sum of several parties' float vectors in one process (the same masks and fixed point
    as the workers): the threshold counts and the tests."""
    ms = [Masker(i) for i in range(len(vectors))]
    for m in ms:
        m.agree([x.public for x in ms])
    total = np.zeros(len(vectors[0]), np.uint64)
    for m, v in zip(ms, vectors):
        total = total + m.mask(encode(v), 0)
    return decode(total)


# ---- bins and prediction ----

def cells(X):
    """Each value's cell on the public grid, per feature (int16)."""
    lo = np.array([g[0] for g in GRID], np.float64)
    w = np.array([(g[1] - g[0]) / CELLS for g in GRID], np.float64)
    return np.clip(np.floor((np.asarray(X, np.float64) - lo) / w), 0, CELLS - 1).astype(np.int16)


def cuts_from_counts(counts, max_bin=256):
    """Bin boundaries (cell indices) per feature from the summed grid counts: every occupied cell its own
    bin if there are at most max_bin of them, else max_bin quantile bins. A value goes to the left of a
    boundary b when its cell is below b."""
    out = []
    for c in counts:
        cum, n = np.cumsum(c), c.sum()
        occ = np.flatnonzero(c > 0)
        if len(occ) <= max_bin:
            b = occ[:-1] + 1
        else:
            b = np.searchsorted(cum, np.arange(1, max_bin) * n / max_bin, side="left") + 1
            b = np.unique(b[(b < CELLS) & (cum[np.minimum(b, CELLS) - 1] < n)])
        out.append(b.astype(np.int16))
    return out


def predict_margin(model, X):
    C = cells(X)
    m = np.full(len(C), model["base_margin"])
    for t in model["trees"]:
        f, b, le, ri, v = (np.asarray(t[k]) for k in ("feature", "cell", "left", "right", "value"))
        node = np.zeros(len(C), np.int64)
        for _ in range(PARAMS["max_depth"] + 1):
            inner = le[node] >= 0
            if not inner.any():
                break
            go_left = C[np.arange(len(C)), np.maximum(f[node], 0)] < b[node]
            node = np.where(inner, np.where(go_left, le[node], ri[node]), node)
        m += v[node]
    return m


def predict_proba(model, X):
    return 1.0 / (1.0 + np.exp(-predict_margin(model, X)))


# ---- training (one worker) ----

def worker(name, rank, address, masked, q, out):
    from multiprocessing.connection import Client
    z = np.load(f"{DATA}/{name}.npz")
    X, y = z["X"], z["y"].astype(np.float64)
    n, d = X.shape
    conn = Client(address, authkey=AUTH)
    conn.send(name)
    mk = Masker(rank)
    conn.send_bytes(mk.public)
    mk.agree(conn.recv())
    st = dict(msg=0, sent=0, recv=0, mask_s=0.0)

    def agg(v):
        u = encode(v)
        if masked:
            t = time.time()
            u = mk.mask(u, st["msg"])
            st["mask_s"] += time.time() - t
        b = u.tobytes()
        conn.send_bytes(b)
        r = conn.recv_bytes()
        st["msg"] += 1
        st["sent"] += len(b)
        st["recv"] += len(r)
        return decode(np.frombuffer(r, np.uint64))

    t0 = time.time()
    C = cells(X)
    counts = np.stack([np.bincount(C[:, j], minlength=CELLS) for j in range(d)])
    total = np.rint(agg(counts.ravel())).astype(np.int64).reshape(d, CELLS)
    bounds = cuts_from_counts(total, PARAMS["max_bin"])
    B = PARAMS["max_bin"]
    bins = np.stack([np.searchsorted(bounds[j], C[:, j], side="right") for j in range(d)], 1)
    base_idx = (np.arange(d) * B)[None, :] + bins                  # per row and feature: f*B + bin
    sy, sn = agg(np.array([y.sum(), float(n)]))
    p0 = sy / sn
    base = float(np.log(p0 / (1 - p0)))
    margin = np.full(n, base)
    lam, mcw, eta = PARAMS["reg_lambda"], PARAMS["min_child_weight"], PARAMS["eta"]
    trees = []
    for _ in range(TREES):
        p = 1.0 / (1.0 + np.exp(-margin))
        g, h = p - y, np.maximum(p * (1 - p), 1e-16)
        T = dict(feature=[-1], cell=[0], threshold=[0.0], left=[-1], right=[-1], value=[0.0])
        level = [0]                                                # tree node ids of the active nodes
        pos = np.zeros(n, np.int64)                                # each row's index in `level`, -1 when done
        known = None                                               # (G, H) of the level's nodes from the split
        for depth in range(PARAMS["max_depth"] + 1):
            A = len(level)
            if depth == PARAMS["max_depth"]:
                G_t, H_t = known
                split = np.zeros(A, bool)
            else:
                r = pos >= 0
                idx = (base_idx[r] + (pos[r] * d * B)[:, None]).ravel()
                Gh = np.bincount(idx, np.repeat(g[r], d), minlength=A * d * B)
                Hh = np.bincount(idx, np.repeat(h[r], d), minlength=A * d * B)
                s = agg(np.concatenate([Gh, Hh]))
                Gs, Hs = s[:A * d * B].reshape(A, d, B), s[A * d * B:].reshape(A, d, B)
                G_t, H_t = Gs[:, 0].sum(1), Hs[:, 0].sum(1)
                GL, HL = np.cumsum(Gs, 2)[:, :, :-1], np.cumsum(Hs, 2)[:, :, :-1]
                GR, HR = G_t[:, None, None] - GL, H_t[:, None, None] - HL
                gain = GL ** 2 / (HL + lam) + GR ** 2 / (HR + lam) - (G_t ** 2 / (H_t + lam))[:, None, None]
                nb = np.array([len(b) for b in bounds])
                ok = (HL >= mcw) & (HR >= mcw) & (np.arange(B - 1)[None, None, :] < nb[None, :, None])
                gain = np.where(ok, gain, -np.inf).reshape(A, -1)
                best = gain.argmax(1)
                split = gain[np.arange(A), best] > RT_EPS
            nxt, child_G, child_H = [], [], []
            new_pos = np.full(n, -1, np.int64)
            for a, node in enumerate(level):
                rows = pos == a
                if not split[a]:
                    w = 0.0 if H_t[a] < mcw else -G_t[a] / (H_t[a] + lam) * eta
                    T["value"][node] = w
                    margin[rows] += w
                    continue
                f, bi = divmod(int(best[a]), B - 1)
                cb = int(bounds[f][bi])
                lo, wd = GRID[f][0], (GRID[f][1] - GRID[f][0]) / CELLS
                kids = []
                for _ in (0, 1):
                    kids.append(len(T["feature"]))
                    for k, v in (("feature", -1), ("cell", 0), ("threshold", 0.0), ("left", -1), ("right", -1),
                                 ("value", 0.0)):
                        T[k].append(v)
                T["feature"][node], T["cell"][node], T["threshold"][node] = f, cb, lo + cb * wd
                T["left"][node], T["right"][node] = kids
                go_left = rows & (C[:, f] < cb)
                new_pos[go_left] = len(nxt)
                new_pos[rows & ~go_left] = len(nxt) + 1
                nxt += kids
                gl, hl = GL[a, f, bi], HL[a, f, bi]
                child_G += [gl, G_t[a] - gl]
                child_H += [hl, H_t[a] - hl]
            if not nxt:
                break
            level, pos, known = nxt, new_pos, (np.array(child_G), np.array(child_H))
        trees.append(T)
    secs = time.time() - t0
    conn.send_bytes(b"")
    conn.close()
    if rank == 0:
        model = dict(params=PARAMS, grid=GRID, cells=CELLS, base_score=p0, base_margin=base, trees=trees)
        json.dump(model, open(out, "w"))
    q.put(dict(client=name, rank=rank, rows=int(n), seconds=round(secs, 1), mask_seconds=round(st["mask_s"], 2),
               messages=st["msg"], payload_sent=st["sent"], payload_received=st["recv"]))


def aggregator(listener, q):
    """Relays the public keys, then adds the workers' (masked) vectors modulo 2^64 and returns the sum."""
    conns = {}
    for _ in CLIENTS:
        c = listener.accept()
        conns[c.recv()] = c
    cs = [conns[k] for k in CLIENTS]
    pubs = [c.recv_bytes() for c in cs]
    for c in cs:
        c.send(pubs)
    n_msg = sent = 0
    while True:
        parts = [c.recv_bytes() for c in cs]
        if not parts[0]:
            break
        total = np.zeros(len(parts[0]) // 8, np.uint64)
        for b in parts:
            total = total + np.frombuffer(b, np.uint64)
        r = total.tobytes()
        for c in cs:
            c.send_bytes(r)
        n_msg += 1
        sent += len(r) * len(cs)
    q.put(dict(client="aggregator", messages=n_msg, payload_sent=sent))


def lo_bytes():
    for line in open("/proc/net/dev"):
        if line.strip().startswith("lo:"):
            return int(line.split(":")[1].split()[8])
    return 0


def train(masked, seed, name):
    from multiprocessing.connection import Listener
    os.makedirs(OUT, exist_ok=True)
    i0, ti = lo_bytes(), time.time()
    time.sleep(IDLE_S)
    idle = (lo_bytes() - i0) / max(time.time() - ti, 1e-9)
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    listener = Listener(("127.0.0.1", 0), authkey=AUTH)
    out = f"{OUT}/{name}.json"
    t0, b0 = time.time(), lo_bytes()
    ag = ctx.Process(target=aggregator, args=(listener, q))
    ag.start()
    ps = [ctx.Process(target=worker, args=(c, i, listener.address, masked, q, out)) for i, c in enumerate(CLIENTS)]
    for p in ps:
        p.start()
    for p in ps + [ag]:
        p.join()
    secs = time.time() - t0
    lb = lo_bytes() - b0 - idle * secs
    info = []
    while not q.empty():
        info.append(q.get())
    m = json.load(open(out))
    fp = hashlib.sha256(json.dumps(m["trees"]).encode()).hexdigest()
    log = dict(masked=masked, seed=seed, trees=len(m["trees"]), seconds=round(secs, 1), loopback_bytes=round(lb),
               idle_bytes_per_s=round(idle), payload_bytes=sum(r["payload_sent"] for r in info),
               model_sha256=fp, parties=sorted(info, key=lambda r: r["client"]),
               exit_codes=[p.exitcode for p in ps + [ag]])
    json.dump(log, open(f"{OUT}/{name}_log.json", "w"), indent=1)
    print(json.dumps(log, indent=1))
    return all(c == 0 for c in log["exit_codes"])


if __name__ == "__main__":
    a = sys.argv[1:]
    masked = "--unmasked" not in a
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    name = f"secagg_{'masked' if masked else 'unmasked'}" + (f"_s{seed}" if seed else "")
    sys.exit(0 if train(masked, seed, name) else 1)
