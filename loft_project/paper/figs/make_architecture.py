"""Draws figs/architecture.pdf, FEVER's architecture as tested in the final campaign
(results/v21/exported/ens_config_fl_ll.json, loftbench/defenses.py EvictBlock, testbed/loft_ryu_app.py).

    ~/.venvs/loft/bin/python paper/figs/make_architecture.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 7.5, "pdf.fonttype": 42, "mathtext.fontset": "stix"})

fig = plt.figure(figsize=(7.1, 2.75))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 142)
ax.set_ylim(0, 55)
ax.axis("off")


def box(x, y, w, h, text, bold=False, dashed=False, size=7.5):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=0.6 if dashed else 0.8,
                           ls=(0, (4, 3)) if dashed else "-", ec="0.45" if dashed else "black"))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
                weight="bold" if bold else "normal", linespacing=1.15)


def arrow(x0, y0, x1, y1, text=None, dx=0, dy=1.2, both=False):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="<|-|>" if both else "-|>",
                                 mutation_scale=6, lw=0.7, color="black", shrinkA=0, shrinkB=0))
    if text:
        ax.text((x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy, text, ha="center", va="bottom", fontsize=6.8,
                style="italic")


# Federated training (left).
box(1, 1, 50, 53, None, dashed=True)
ax.text(26, 50.6, "Federated training (offline)", ha="center", fontsize=8, weight="bold")
for i, (c, seen) in enumerate((("C1", "univ2: G1, Mimic"), ("C2", "univ2: G2, Spoof"), ("C3", "bigFlows: G3, Pulse"))):
    y = 39 - i * 10.5
    box(4, y, 20, 8.5, f"Controller {c}\n{seen}", size=6.8)
    arrow(24, y + 4.25, 30, 30 - i * 3)
box(30, 19, 18, 16, "Aggregator\nsums per-bin\ngradient and\nhessian histograms", size=6.8)
box(4, 3, 44, 8, "Shared XGBoost detector (300 trees, depth 6)\nthreshold: 0.1 % false alarms on benign runs",
    size=6.8)
arrow(39, 19, 39, 11)
ax.text(5, 13.4, "no rows or labels leave a controller", ha="left", fontsize=6.3, style="italic")

# Online loop (right): three columns, three rows.
box(55, 1, 86, 53, None, dashed=True)
ax.text(98, 50.6, "Detection and response at each switch (online, every 1 s)", ha="center", fontsize=8,
        weight="bold")
X1, X2, X3, W = 58, 86.5, 115, 24
Y1, Y2, Y3, H = 37, 21.5, 6, 10
box(X1, Y1, W, H, "Switch flow table\n(3,500 entries,\nidle timeout 10 s)", size=6.8)
box(X2, Y1, W, H, "Flow statistics\n(OpenFlow poll)")
box(X3, Y1, W, H, "Table occupancy\n$\\geq \\rho$ = 70 %?")
box(X2, Y2, W, H, "Volume rule (table $\\geq$ 90 %):\nhost holds $>X$ entries\nand $\\geq 3\\times$ the median", size=6.5)
box(X3, Y2, W, H, "17 features of\neach changed entry")
box(X1, Y3, W, H, "Permanent block:\ndrop rule at the host's\naccess-switch ingress", size=6.8)
box(X2, Y3, W, H, "Eviction rule:\nhost with outlier\nevictions in 10 s", size=6.8)
box(X3, Y3, W, H, "Score $\\geq \\tau$:\nevict the entry")
arrow(X1 + W, Y1 + H / 2, X2, Y1 + H / 2)
arrow(X2 + W, Y1 + H / 2, X3, Y1 + H / 2)
arrow(X3 + W / 2, Y1, X3 + W / 2, Y2 + H, "yes", dx=2.4, dy=0.4)
arrow(X3, Y1 + 1.5, X2 + W, Y2 + H - 1.5)
arrow(X3 + W / 2, Y2, X3 + W / 2, Y3 + H)
arrow(X3, Y3 + H / 2, X2 + W, Y3 + H / 2)
arrow(X2, Y3 + H / 2, X1 + W, Y3 + H / 2)
arrow(X2, Y2 + 1.5, X1 + W, Y3 + H - 1.5)
arrow(X1 + W / 2, Y3 + H, X1 + W / 2, Y1)
ax.plot([48, X3 + W / 2], [3.3, 3.3], color="black", lw=0.7)
arrow(X3 + W / 2, 3.3, X3 + W / 2, Y3)
ax.text(70, 3.9, "detector", ha="center", fontsize=6.3, style="italic")

fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.pdf"))
fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png"), dpi=200)
