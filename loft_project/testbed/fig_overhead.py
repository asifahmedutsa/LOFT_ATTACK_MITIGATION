"""System overhead of deploying FEVER, in the layout of FTODefender's Fig. 13: (a) CPU usage and
(b) memory (RSS) of the controller process over time, with and without FEVER, dashed lines at the
means. v5 campaign, T1B, seed 4140; pidstat samples aligned to the run clock.

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_overhead.py [A2|A4|E9P]   # results/paper_figs/v6/fig22_overhead_<attack>.*
"""
import os
import sys
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

V = sys.argv[1] if len(sys.argv) > 1 else "A2"


def series(defense, kind):
    d = os.path.expanduser(f"~/loft-runs/v5_T1B_{V}_{defense}_s4140")
    t0 = datetime.fromtimestamp(float(open(f"{d}/controller_T1B_t0.txt").read()))
    t0s = t0.hour * 3600 + t0.minute * 60 + t0.second + t0.microsecond / 1e6
    t, y = [], []
    for line in open(f"{d}/{kind}_pidstat.txt"):
        f = line.split()
        if len(f) > 3 and f[-1] == "python3.8" and f[0][0].isdigit():
            x = datetime.strptime(f[0] + f[1], "%I:%M:%S%p")
            t.append((x.hour * 3600 + x.minute * 60 + x.second - t0s) % 86400)
            y.append(float(f[-3]) if kind == "cpu" else float(f[-3]) / 1024)
    return np.array(t), np.array(y)


fig, axs = plt.subplots(1, 2, figsize=(9, 3.3))
for ax, kind, ylab, cap in ((axs[0], "cpu", "CPU usage of the controller (%)", "(a) CPU utilization"),
                            (axs[1], "mem", "Memory of the controller (MB)", "(b) Memory consumption")):
    for d, lab, col, mk in (("ensguard-v6", "With FEVER", "#3a8fd0", "o"), ("none", "Without FEVER", "#f39c3c", "^")):
        t, y = series(d, kind)
        ax.plot(t, y, "-" + mk, color=col, ms=2.5, lw=0.8, label=lab)
        ax.axhline(y[t >= 50].mean(), color=col, lw=0.9, ls="--")
    ax.set_xlim(0, 310)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylab)
    ax.legend(fontsize=8, loc="lower right")
    ax.text(0.5, -0.27, cap, transform=ax.transAxes, ha="center", va="top", fontsize=12)
fig.tight_layout(w_pad=3)
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v6/fig22_overhead_{V}.{ext}", dpi=200, bbox_inches="tight")
for d in ("ensguard-v6", "none"):
    tc, c = series(d, "cpu")
    tm, m = series(d, "mem")
    print(d, "CPU after attack %.1f %%, memory mean %.0f MB, max %.0f MB" % (c[tc >= 50].mean(), m[tm >= 50].mean(), m.max()))
