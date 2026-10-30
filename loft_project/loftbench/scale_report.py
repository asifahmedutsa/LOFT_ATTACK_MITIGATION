"""Tables for the controller-scaling experiment (loftbench/scale.py).

  PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.scale_report

Exposure is relative to the federation of size K, so the local models' online rows (run once,
K = 0) are relabelled for each K. Means are over controllers, variants, training seeds and
episode seeds; 95 % intervals over the training seeds (offline) or over controllers (online).
Writes results/scale/{offline_summary.csv, online_summary.csv, fixed_c1c3.csv}.
"""
import os

import numpy as np
import pandas as pd

from .scale import KS, OUT, _ctrl, exposure


def _ci(x):
    x = np.asarray(x, float)
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def main():
    off = pd.read_csv(os.path.join(OUT, "offline.csv"))
    on = pd.read_csv(os.path.join(OUT, "online.csv"))
    loc = on[on.training == "local"]
    parts = [on[on.training.isin(["fedavg", "pooled"])]]
    for k in KS:
        x = loc[loc.controller.isin(_ctrl(k))].copy()
        x["K"] = k
        x["exposure"] = [exposure(c, v, k) for c, v in zip(x.controller, x.variant)]
        parts.append(x)
    none = on[on.training == "none"]
    for k in KS:
        x = none[none.controller.isin(_ctrl(k))].copy()
        x["K"] = k
        x["exposure"] = [exposure(c, v, k) for c, v in zip(x.controller, x.variant)]
        parts.append(x)
    on = pd.concat(parts)

    rows = []
    for (k, t, e), g in off.groupby(["K", "training", "exposure"]):
        per_seed = g.groupby("train_seed")[["precision", "recall", "f1", "accuracy"]].mean() * 100
        rows.append(dict(K=k, training=t, exposure=e, n=len(g),
                         **{m: round(per_seed[m].mean(), 2) for m in per_seed},
                         f1_ci=round(_ci(per_seed["f1"]), 2)))
    for (k, t), g in off.groupby(["K", "training"]):
        per_seed = g.groupby("train_seed")[["precision", "recall", "f1", "accuracy"]].mean() * 100
        rows.append(dict(K=k, training=t, exposure="all", n=len(g),
                         **{m: round(per_seed[m].mean(), 2) for m in per_seed},
                         f1_ci=round(_ci(per_seed["f1"]), 2)))
    offs = pd.DataFrame(rows).sort_values(["exposure", "K", "training"])
    offs.to_csv(os.path.join(OUT, "offline_summary.csv"), index=False)

    rows = []
    for (k, t, e), g in list(on.groupby(["K", "training", "exposure"])) + \
            [((k, t, "all"), g) for (k, t), g in on.groupby(["K", "training"])]:
        per_c = g.groupby("controller").harmed.mean()
        rows.append(dict(K=k, training=t, exposure=e, episodes=len(g),
                         harmed_mean=round(g.harmed.mean(), 2), harmed_ci=round(_ci(per_c), 2),
                         harmed_p90=round(g.harmed.quantile(.9), 2),
                         benign_demotes=round(g.benign_demotes.mean(), 1)))
    ons = pd.DataFrame(rows).sort_values(["exposure", "K", "training"])
    ons.to_csv(os.path.join(OUT, "online_summary.csv"), index=False)

    # Controllers C1-C3 are in every federation: same controllers, same test cells, only K changes.
    fx = on[on.controller.isin(_ctrl(3))]
    fxo = off[off.controller.isin(_ctrl(3))]
    rows = []
    for (k, t), g in fx.groupby(["K", "training"]):
        o = fxo[(fxo.K == k) & (fxo.training == t)] if t != "none" else None
        rows.append(dict(K=k, training=t, harmed_mean=round(g.harmed.mean(), 2),
                         harmed_on_A4_A5_A7=round(g[g.variant.isin(["A4", "A5", "A7"])].harmed.mean(), 2),
                         recall=round(100 * o.recall.mean(), 2) if o is not None else "",
                         f1=round(100 * o.f1.mean(), 2) if o is not None else ""))
    fxs = pd.DataFrame(rows)
    fxs.to_csv(os.path.join(OUT, "fixed_c1c3.csv"), index=False)

    pd.set_option("display.width", 200)
    print("== offline (mean over controllers x variants), by exposure ==")
    print(offs.to_string(index=False))
    print("\n== online benign flows harmed % ==")
    print(ons.to_string(index=False))
    print("\n== controllers C1-C3 only, as K grows ==")
    print(fxs.to_string(index=False))


if __name__ == "__main__":
    main()
