"""Draws docs/loft_attack_explained.png: (a) a normal rule expires 10 s after its last packet;
(b) a LOFT rule is refreshed just before the timeout and never expires; (c) the core table of a
testbed run with no defense under A2 (v5_T1B_A2_none_s4140), filling with attack rules.

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_loft_fig.py
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.spines.top": False,
                     "axes.spines.right": False})
RUN = os.path.expanduser("~/loft-runs/v5_T1B_A2_none_s4140")
ATT = {"00:00:00:00:01:05", "00:00:00:00:01:06"}
CAP, TO = 3500, 10.0

fig = plt.figure(figsize=(9, 5.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.35], hspace=0.55, wspace=0.25)


def lifeline(ax, pkts, end, title):
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 1.6)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.axhspan(0.35, 0.75, xmin=pkts[0] / 40, xmax=min(end, 40) / 40, color="#bcbcbc")
    ax.vlines(pkts, 0.8, 1.25, color="black", lw=1.4)
    ax.text(0.3, 1.38, "packets", fontsize=8)
    ax.text(0.3, 0.12, "rule in the table", fontsize=8)
    if end < 40:
        ax.annotate("", xy=(end, 0.9), xytext=(pkts[-1], 0.9),
                    arrowprops=dict(arrowstyle="<->", lw=0.8))
        ax.text((pkts[-1] + end) / 2, 0.95, "10 s idle", ha="center", fontsize=8)
        ax.text(end + 0.5, 0.48, "rule removed", fontsize=8)
    ax.set_xlabel("time (s)")
    ax.set_title(title, fontsize=9.5, loc="left")


lifeline(fig.add_subplot(gs[0, 0]), [2, 3, 4.5, 6, 7], 17, "(a) Normal connection")
atk = list(np.arange(2, 40, 9.0))
lifeline(fig.add_subplot(gs[0, 1]), atk, 40, "(b) LOFT: one packet every 9 s")

t, tot = [], []
for r in csv.DictReader(open(f"{RUN}/switch_T1B_s11.csv")):
    t.append(float(r["t"]))
    tot.append(int(r["entries"]))
a = {}
for r in csv.DictReader(open(f"{RUN}/switch_T1B_s11_macs.csv")):
    if r["mac"] in ATT:
        a[float(r["t"])] = a.get(float(r["t"]), 0) + int(r["entries"])
att = np.array([a.get(x, 0) for x in t])
ax = fig.add_subplot(gs[1, :])
ax.fill_between(t, 0, np.array(tot) - att, color="#9ab7d3", lw=0, label="normal rules")
ax.fill_between(t, np.array(tot) - att, tot, color="#d98b6a", lw=0, label="attack rules")
ax.axhline(CAP, color="black", lw=0.9, ls="--")
ax.text(3, CAP + 60, "table limit (3,500 rules)", fontsize=8)
ax.axvline(50, color="black", lw=0.8, ls=":")
ax.text(51, 300, "attack starts", fontsize=8)
ax.set_xlim(0, 300)
ax.set_ylim(0, CAP * 1.12)
ax.set_xlabel("time (s)")
ax.set_ylabel("rules in the core switch")
ax.legend(loc="upper left", bbox_to_anchor=(0.19, 0.92), frameon=False, fontsize=8)
ax.set_title("(c) Testbed, no defense, attack A2", fontsize=9.5, loc="left")
fig.savefig("docs/loft_attack_explained.png", dpi=200, bbox_inches="tight")
print("wrote docs/loft_attack_explained.png")
