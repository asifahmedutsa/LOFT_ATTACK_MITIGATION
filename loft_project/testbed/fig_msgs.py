"""Packet-In and Table-Full messages per second at the controller, in the layout of DMS-BTT's
Fig. 8: (a) no attack, (b) attack without defense, (c) attack with FEVER. v5 campaign, T1B,
seed 4140 (controller_T1B.csv holds the cumulative counters per poll).

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_msgs.py [A2|A4|E9P]   # results/paper_figs/v5/fig19_messages_<attack>.*
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

V = sys.argv[1] if len(sys.argv) > 1 else "A2"
SEED = 4140


def rates(variant, defense):
    c = pd.read_csv(os.path.expanduser(f"~/loft-runs/v5_T1B_{variant}_{defense}_s{SEED}/controller_T1B.csv"))
    dt = np.diff(c.t.values)
    keep = dt > 0
    t = c.t.values[1:][keep]
    pin = np.diff(c.packet_in.values)[keep] / dt[keep]
    tf = np.diff(c.table_full.values)[keep] / dt[keep]
    return t, pin, tf


fig = plt.figure(figsize=(11, 8.2))
gs = fig.add_gridspec(2, 4, hspace=0.62, wspace=0.55)
panels = [(gs[0, 0:2], "benign", "none", "(a) No LFTO attack in the network."),
          (gs[0, 2:4], V, "none", "(b) LFTO attack launched and FEVER not deployed."),
          (gs[1, 1:3], V, "ensguard-v5", "(c) LFTO attack launched and FEVER deployed.")]
data = []
for spec, v, d, cap in panels:
    t, pin, tf = rates(v, d)
    data.append((spec, t, pin, tf, cap))
for spec, t, pin, tf, cap in data:
    ax = fig.add_subplot(spec)
    ax.plot(t, pin, "-o", color="#4da6e8", ms=3, lw=0.8, label="Packet-In")
    ax.plot(t, tf, "-^", color="#e8191f", ms=3, lw=0.8, label="Table-Full")
    ax.set_xlim(0, 310)
    hi = max(pin.max(), tf.max())
    ax.set_ylim(-0.03 * hi, hi * 1.08)
    ax.set_xlabel("Time(s)", fontsize=8)
    ax.set_ylabel("Number of messages")
    ax.legend(loc="upper left", fontsize=8.5)
    ax.text(0.5, -0.24, cap, transform=ax.transAxes, ha="center", va="top", fontsize=13, wrap=True)
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v5/fig19_messages_{V}.{ext}", dpi=200, bbox_inches="tight")
print("wrote", f"fig19_messages_{V}")
