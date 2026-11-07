"""Ablation of FEVER on the testbed: benign flows harmed and the attacker's share of the core table
per attack, for FEVER, FEVER without the volume block and FEVER without ML (bar = mean, dot = one
seed). Reads results/fever_comparison/runs.csv (docs/build_comparison.py).

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_ablation.py   # results/paper_figs/v5/fig23_ablation.*
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from loftbench.config import ATTACK_NAMES  # noqa: E402

d = pd.read_csv("results/fever_comparison/runs.csv")
ATT = ["A2", "A4", "E9P"]
V = [("ensguard-v5", "FEVER", "#3a6fb0", None), ("ensguard-v4lite", "FEVER without volume block", "#9ec3e6", "//"),
     ("ensguard-v5-noml", "FEVER without ML", "#f0a35e", "..")]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
x = np.arange(len(ATT))
w = 0.26
for ax, key, ylab, cap in ((axs[0], "harm", "Normal flows harmed (%)", "(a) Normal flows harmed."),
                           (axs[1], "share", "Attacker's share of the flow table (%)", "(b) Attacker's share of the flow table.")):
    for j, (k, lab, col, hatch) in enumerate(V):
        m = [d[(d.defense == k) & (d.variant == v)][key].mean() for v in ATT]
        ax.bar(x + (j - 1) * w, m, w * 0.92, color=col, edgecolor="black", lw=0.6, hatch=hatch, label=lab)
        for i, v in enumerate(ATT):
            y = d[(d.defense == k) & (d.variant == v)][key].values
            ax.plot(np.full(len(y), x[i] + (j - 1) * w), y, "o", ms=2.5, color="black")
    ax.set_xticks(x, [ATTACK_NAMES[v] for v in ATT])
    ax.set_ylabel(ylab)
    ax.text(0.5, -0.17, cap, transform=ax.transAxes, ha="center", va="top", fontsize=11)
axs[0].legend(fontsize=8.5, frameon=False, loc="upper left")
fig.tight_layout(w_pad=3)
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v5/fig23_ablation.{ext}", dpi=200, bbox_inches="tight")
print("wrote fig23_ablation")
