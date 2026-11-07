"""CPU usage of the controller process (Ryu, python3.8, pidstat every 1 s) over time, in the
layout of DMS-BTT's Fig. 10: attack without FEVER, attack with FEVER, and no attack with FEVER.
v5 campaign, T1B, seed 4140.

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_cpu.py [A2|A4|E9P]   # results/paper_figs/v5/fig21_cpu_<attack>.*
"""
import os
import sys
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

V = sys.argv[1] if len(sys.argv) > 1 else "A2"


def cpu(variant, defense):
    """Seconds on the run's clock (controller_T1B_t0.txt, the time the run's t = 0 refers to) and %CPU."""
    d = os.path.expanduser(f"~/loft-runs/v5_T1B_{variant}_{defense}_s4140")
    t0 = datetime.fromtimestamp(float(open(f"{d}/controller_T1B_t0.txt").read()))
    t0s = t0.hour * 3600 + t0.minute * 60 + t0.second + t0.microsecond / 1e6
    t, c = [], []
    for line in open(f"{d}/cpu_pidstat.txt"):
        f = line.split()
        if len(f) > 3 and f[-1] == "python3.8" and f[0][0].isdigit():
            x = datetime.strptime(f[0] + f[1], "%I:%M:%S%p")
            t.append((x.hour * 3600 + x.minute * 60 + x.second - t0s) % 86400)
            c.append(float(f[-3]))
    return np.array(t), np.array(c)


fig, ax = plt.subplots(figsize=(6.6, 3.6))
for (v, d, lab, col, mk) in ((V, "none", "LFTO attack without FEVER", "#f0505a", "o"),
                            (V, "ensguard-v5", "LFTO attack with FEVER", "#4da6e8", "^"),
                            ("benign", "ensguard-v5", "No LFTO attack, FEVER deployed", "#f2c200", "D")):
    t, c = cpu(v, d)
    ax.plot(t, c, "-" + mk, color=col, ms=3, lw=0.8, alpha=0.85, label=lab)
ax.set_xlim(0, 310)
ax.set_ylim(0, 105)
ax.set_xlabel("Time(s)")
ax.set_ylabel("CPU usage of the controller (%)")
ax.legend(loc="lower right", fontsize=8)
ax.axvline(50, color="gray", lw=0.8, ls=":")
ax.text(52, 8, "attack starts", fontsize=8, color="gray")
ax.text(0.5, -0.24, f"CPU usage of the controller with and without FEVER ({V} attack).", transform=ax.transAxes,
        ha="center", va="top", fontsize=10)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v5/fig21_cpu_{V}.{ext}", dpi=200, bbox_inches="tight")
for v, d in ((V, "none"), (V, "ensguard-v5"), ("benign", "ensguard-v5")):
    t, c = cpu(v, d)
    print(v, d, "mean CPU before 50 s %.1f, after %.1f" % (c[t < 50].mean(), c[t >= 50].mean()))
