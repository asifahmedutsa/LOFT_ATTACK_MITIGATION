"""APIT (average packet inter-arrival time of the flow table, DMS-BTT Eq. 3) before and after the
attack, with no defense, in the style of DMS-BTT's Fig. 2(a). Per poll at the core switch s11:
APIT = mean over the entries of Time_i / Num_pi, with Time_i the entry's age and Num_pi its
packet count (an entry with no packet counts its age, as in DMS-BTT's Algorithm 1).

The v5 campaign runs carry no per-entry counters, so the data are the no-defense recordings made
with the entry log for the volume-block calibration (~/loft-runs/v5vol_T1A_<attack>_none_s4153:
same testbed and settings, the T1A part of the trace).

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_apit.py   # results/paper_figs/v5/fig18_apit_no_defense.*
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "testbed")
from entrylog import read_entries  # noqa: E402

CAP, T_ATT = 3500, 50.0
SHADE = ("#cfe2f7", "#fbf1c4", "#f8cccc")


def apit(run):
    ts, ys = [], []
    for t, fids, pk, by, inst, _ in read_entries(f"{run}/switch_T1A_s11_entries.bin"):
        if len(fids) == 0:
            continue
        age = np.maximum(t - inst, 0.0)
        ts.append(t)
        ys.append(float(np.mean(np.where(pk > 0, age / np.maximum(pk, 1), age))))
    return np.array(ts), np.array(ys)


fig, axs = plt.subplots(1, 3, figsize=(14, 3.9), sharey=True)
for ax, v, letter in zip(axs, ("A2", "A4", "E9P"), "abc"):
    run = os.path.expanduser(f"~/loft-runs/v5vol_T1A_{v}_none_s4153")
    t, y = apit(run)
    s = pd.read_csv(f"{run}/switch_T1A_s11.csv")
    full = s[s.entries >= 0.98 * CAP].t
    t_full = float(full.min()) if len(full) else float(t.max())
    for (a, b), c in zip(((0, T_ATT), (T_ATT, t_full), (t_full, t.max())), SHADE):
        ax.axvspan(a, b, color=c, lw=0)
    for x in (T_ATT, t_full):
        ax.axvline(x, color="black", lw=1.1)
    ax.plot(t, y, color="black", lw=1.0)
    ax.set_xlim(0, t.max())
    ax.set_xlabel("Time(s)")
    ax.text(0.5, -0.24, f"({letter}) APIT before and after {v}.", transform=ax.transAxes, ha="center",
            va="top", fontsize=12)
    pre, mid, post = (y[(t >= 15) & (t < T_ATT)].mean(), y[(t >= T_ATT) & (t < t_full)].mean(), y[t >= t_full].mean())
    print(f"{v}: table full at {t_full:.0f} s; mean APIT before {pre:.2f} s, filling {mid:.2f} s, full {post:.2f} s")
axs[0].set_ylabel("APIT(s)")
fig.tight_layout(w_pad=2)
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v5/fig18_apit_no_defense.{ext}", dpi=200, bbox_inches="tight")
