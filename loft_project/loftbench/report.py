"""Tables, statistics and figures from experiment artifacts.

Uncertainty: 95% percentile bootstrap over independent episodes
(domain x variant x seed). Significance: paired Wilcoxon signed-rank tests of
FL-DualGuard against each defense on identical traffic, Holm-corrected.
"""
import json
import os
import pickle

import numpy as np
import pandas as pd

PROPOSED = "fl-dualguard"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRAY, INK, MUTED = "#a3a29c", "#0b0b0b", "#52514e"

LABEL = {
    "none": "No defense", "ovs-evict": "OVS evict", "threshold-lru": "Threshold-LRU",
    "dms-btt": "DMS-BTT (reimpl.)", "dg-local-svmrf": "Local SVM-RF + DG policy",
    "dg-local": "Local MLP + DG policy", "dg-fedavg": "FedAvg + DG policy",
    "fl-dualguard": "FL-DualGuard (ours)", "dg-pooled": "Centralized pooled (oracle)",
    "abl-nosoft": "w/o soft demotion", "abl-nohard": "w/o hard overflow guard",
    "abl-nocalib": "w/o budget calibration", "abl-nosrc": "w/o source features",
    "abl-noctx": "w/o context features",
}
MAIN = ["none", "ovs-evict", "threshold-lru", "dms-btt", "dg-local-svmrf", "dg-local",
        "dg-fedavg", "fl-dualguard", "dg-pooled"]
ABL = ["fl-dualguard", "abl-nosoft", "abl-nohard", "abl-nocalib", "abl-nosrc", "abl-noctx"]
METRICS = [
    # summarize() stores each metric already multiplied by its scale.
    ("benign_flows_impacted_frac", "Benign flows impacted (%)", 100),
    ("benign_flows_rejected_frac", "Benign flows rejected (%)", 100),
    ("benign_flows_evicted_frac", "Benign flows evicted/demoted (%)", 100),
    ("avg_attack_occ_post", "Malicious occupancy after onset (%)", 100),
    ("overflow_seconds_post_attack", "Overflow time (s)", 1),
    ("packet_in", "Packet-In messages (k)", 1e-3),
    ("decision_ms_mean", "Decision loop (ms, mean)", 1),
]


def boot_ci(x, n=2000, seed=0):
    x = np.asarray(x, float)
    r = np.random.default_rng(seed)
    means = x[r.integers(0, len(x), (n, len(x)))].mean(1)
    return x.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(pvals) - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


def summarize(df, defenses, attack_only=True):
    sub = df[df.variant != "benign"] if attack_only else df
    rows = []
    for dname in defenses:
        g = sub[sub.defense == dname]
        if g.empty:
            continue
        row = {"defense": LABEL.get(dname, dname), "key": dname, "episodes": len(g)}
        for m, lab, scale in METRICS:
            mu, lo, hi = boot_ci(g[m] * scale)
            row[lab] = f"{mu:.2f} [{lo:.2f}, {hi:.2f}]"
            row[m] = mu
        rows.append(row)
    return pd.DataFrame(rows)


def paired_tests(df, metric, against):
    from scipy.stats import wilcoxon
    key = ["domain", "variant", "seed"]
    base = df[df.defense == PROPOSED].set_index(key)[metric]
    out = []
    for d in against:
        if d == PROPOSED:
            continue
        other = df[df.defense == d].set_index(key)[metric]
        j = base.to_frame("p").join(other.to_frame("o"), how="inner")
        diff = j.p - j.o
        if (diff == 0).all():
            p = 1.0
        else:
            p = wilcoxon(j.p, j.o, zero_method="zsplit").pvalue
        out.append(dict(baseline=LABEL.get(d, d), n_pairs=len(j), metric=metric,
                        mean_diff=float(diff.mean()), wins=int((diff < 0).sum()),
                        ties=int((diff == 0).sum()), losses=int((diff > 0).sum()), p=float(p)))
    t = pd.DataFrame(out)
    if len(t):
        t["p_holm"] = holm(t.p.values)
    return t


def _style(plt):
    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e0",
        "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
        "savefig.dpi": 200, "savefig.bbox": "tight", "font.family": "DejaVu Sans",
    })


def _hbar(ax, df, metric, scale, title):
    df = df.sort_values(metric)
    y = np.arange(len(df))
    vals = df[metric].values
    cols = [BLUE if k == PROPOSED else GRAY for k in df.key]
    ax.barh(y, vals, color=cols, height=0.62)
    for yi, v in zip(y, vals):
        ax.text(v, yi, f" {v:.1f}", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, df.defense)
    ax.set_title(title, fontsize=9, loc="left", color=INK)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(vals.max() * 1.18, 1e-3))


def figures(out, df, offline, info, series):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    fig_dir = os.path.join(out, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    def save(fig, name):
        fig.savefig(os.path.join(fig_dir, name + ".png"))
        fig.savefig(os.path.join(fig_dir, name + ".pdf"))
        plt.close(fig)

    # Fig 1: occupancy timelines.
    cases = [("D1", "A2"), ("D2", "A6"), ("D3", "A4")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 2.6), sharey=True)
    for ax, (d, v) in zip(axes, cases):
        for dname, col in (("none", ORANGE), ("dms-btt", AQUA), (PROPOSED, BLUE)):
            ts = series.get((dname, d, v))
            if not ts:
                continue
            t = [r["t"] for r in ts]
            ax.plot(t, [100 * r["occupancy"] for r in ts], color=col, lw=1.1,
                    label=LABEL[dname])
        ax.axvline(50, color=MUTED, lw=0.8, ls="--")
        ax.set_title(f"{d} / {v}", fontsize=9, loc="left")
        ax.set_xlabel("Time (s)")
    axes[0].set_ylabel("Flow-table occupancy (%)")
    axes[0].legend(loc="lower right", fontsize=7.5)
    save(fig, "fig1_occupancy_timeline")

    # Fig 2: main comparison.
    s = summarize(df, MAIN)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2))
    _hbar(axes[0], s, "benign_flows_impacted_frac", 1, "Benign flows impacted (%) - lower is better")
    _hbar(axes[1], s, "avg_attack_occ_post", 1, "Malicious table occupancy after onset (%)")
    fig.tight_layout()
    save(fig, "fig2_main_comparison")

    # Fig 3: offline AUC heatmap by exposure group.
    off = pd.DataFrame(offline)
    piv = off.groupby(["detector", "exposure"]).auc.mean().unstack()
    order = [c for c in ["seen-local", "seen-remote", "unseen-all"] if c in piv.columns]
    rows = [r for r in ["dms-btt-flow", "local-svmrf", "local-mlp", "fedavg", "fedprox",
                        "fedprox-nosrc", "pooled"] if r in piv.index]
    piv = piv.loc[rows, order]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    im = ax.imshow(piv.values, cmap="Blues", vmin=0.5, vmax=1.0, aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8,
                    color="white" if v > 0.85 else INK)
    ax.set_xticks(range(len(order)), ["seen locally", "seen by other\ncontrollers", "unseen by all\n(A6)"])
    ax.set_yticks(range(len(rows)), rows)
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Per-entry ROC AUC")
    save(fig, "fig3_offline_auc_exposure")

    # Fig 4: federated convergence.
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    for name, col in (("fedavg", ORANGE), ("fedprox", BLUE)):
        h = info.get(name, {}).get("history", [])
        if h:
            ax.plot([r["round"] for r in h], [r["val_auc"] for r in h], color=col, lw=2,
                    label="FedAvg" if name == "fedavg" else "FedProx (ours)")
    ax.set_xlabel("Federated round")
    ax.set_ylabel("Mean validation AUC")
    ax.legend(loc="lower right")
    save(fig, "fig4_fl_convergence")

    # Fig 5: ablation.
    a = summarize(df, ABL)
    fig, axes = plt.subplots(1, 2, figsize=(11, 2.6))
    _hbar(axes[0], a, "benign_flows_impacted_frac", 1, "Benign flows impacted (%)")
    _hbar(axes[1], a, "avg_attack_occ_post", 1, "Malicious occupancy after onset (%)")
    fig.tight_layout(w_pad=4)
    save(fig, "fig5_ablation")

    # Fig 6: per-variant benign impact for three key defenses.
    fig, ax = plt.subplots(figsize=(7, 2.8))
    variants = sorted(v for v in df.variant.unique() if v != "benign")
    w = 0.26
    for i, (dname, col) in enumerate((("dms-btt", AQUA), ("dg-local", ORANGE), (PROPOSED, BLUE))):
        g = df[df.defense == dname].groupby("variant").benign_flows_impacted_frac.mean() * 100
        ax.bar(np.arange(len(variants)) + (i - 1) * w, [g.get(v, np.nan) for v in variants],
               width=w - 0.03, color=col, label=LABEL[dname])
    ax.set_xticks(range(len(variants)), variants)
    ax.set_ylabel("Benign flows impacted (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=7.5)
    save(fig, "fig6_per_variant")


def report(out):
    df = pd.read_csv(os.path.join(out, "online_episodes.csv"))
    tdir = os.path.join(out, "tables")
    os.makedirs(tdir, exist_ok=True)
    cols = ["defense", "episodes"] + [lab for _, lab, _ in METRICS]
    summarize(df, MAIN)[cols].to_csv(os.path.join(tdir, "table_main_attack.csv"), index=False)
    summarize(df[df.variant == "benign"], MAIN, attack_only=False)[cols].to_csv(
        os.path.join(tdir, "table_benign_only.csv"), index=False)
    summarize(df, ABL)[cols].to_csv(os.path.join(tdir, "table_ablation.csv"), index=False)
    for dom in sorted(df.domain.unique()):
        summarize(df[df.domain == dom], MAIN)[cols].to_csv(
            os.path.join(tdir, f"table_main_{dom}.csv"), index=False)
    unseen = df[df.variant == "A6"]
    summarize(unseen, MAIN)[cols].to_csv(os.path.join(tdir, "table_unseen_A6.csv"), index=False)
    att = df[df.variant != "benign"]
    tests = pd.concat([paired_tests(att, m, MAIN + ABL) for m in
                       ("benign_flows_impacted_frac", "avg_attack_occ_post")])
    tests.to_csv(os.path.join(tdir, "paired_tests.csv"), index=False)

    off = pd.read_csv(os.path.join(out, "offline_detection.csv"))
    off.groupby(["detector", "exposure"])[["auc", "tpr_at_1fpr", "precision", "recall", "f1", "fpr"]] \
        .mean().round(4).to_csv(os.path.join(tdir, "table_offline_by_exposure.csv"))
    off.groupby(["detector", "variant"]).auc.mean().unstack().round(4).to_csv(
        os.path.join(tdir, "table_offline_auc_by_variant.csv"))
    info = json.load(open(os.path.join(out, "train_info.json")))
    series = pickle.load(open(os.path.join(out, "online_timeseries.pkl"), "rb"))
    figures(out, df, off.to_dict("records"), info, series)
    print(f"tables -> {tdir}; figures -> {os.path.join(out, 'figures')}")
