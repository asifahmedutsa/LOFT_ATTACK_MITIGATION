"""Percentage of malicious flows in the core flow table (attack entries / table capacity) over
time with FEVER deployed, in the layout of DMS-BTT's Fig. 7. v5 campaign, T1B, seed 4140.

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_malicious_share.py [A2]   # results/paper_figs/v5/fig20_malicious_share_<attack>.*
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

V = sys.argv[1] if len(sys.argv) > 1 else "A2"
CAP = 3500
ATT = {"00:00:00:00:01:05", "00:00:00:00:01:06"}
run = os.path.expanduser(f"~/loft-runs/v5_T1B_{V}_ensguard-v5_s4140")
m = pd.read_csv(f"{run}/switch_T1B_s11_macs.csv")
s = pd.read_csv(f"{run}/switch_T1B_s11.csv")
att = m[m.mac.isin(ATT)].groupby("t").entries.sum().reindex(s.t, fill_value=0)
share = 100 * att.values / CAP

fig, ax = plt.subplots(figsize=(6.4, 3.3))
ax.plot(s.t, share, "-o", color="red", ms=3, lw=1.1)
ax.set_xlim(-5, 310)
ax.set_ylim(0, 100)
ax.set_xlabel("Time(s)")
ax.set_ylabel("Malicious flows in the\nflow table (%)")
ax.axvline(50, color="gray", lw=0.8, ls=":")
ax.text(52, 93, "attack starts", fontsize=8, color="gray", va="top")
ax.text(0.5, -0.3, f"Percentage of malicious flows in the flow table with FEVER deployed ({V} attack).",
        transform=ax.transAxes, ha="center", va="top", fontsize=10)
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v5/fig20_malicious_share_{V}.{ext}", dpi=200, bbox_inches="tight")
print(f"peak {share.max():.1f} %, mean after 50 s {share[s.t >= 50].mean():.1f} %")
