"""FEVER's counterpart of DMS-BTT's Fig. 2: the two signals FEVER acts on, over one undefended
attack run, shaded by network state (before the attack / attack filling the table / table full).
  (a) entries in the core table s11, with FEVER's occupancy thresholds TH1 (70 %) and TH2 (90 %);
  (b) entries held per host at s11: each attacker and the busiest normal host, with the volume
      limit X (results/v21/exported/ens_config_v5.json).
Data: the v5 campaign's no-defense run (defense none), T1B, seed 4140.

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_states.py [A4|A2|E9P]   # results/paper_figs/v6/fig17_states_<attack>.*
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

V = sys.argv[1] if len(sys.argv) > 1 else "A4"
RUN = os.path.expanduser(f"~/loft-runs/v5_T1B_{V}_none_s4140")
CAP, T_ATT, RHO1, RHO2 = 3500, 50.0, 0.7, 0.9
X = json.load(open("results/v21/exported/ens_config_v5.json"))["block"]["vol_x"]["T1B"]["s11"]
ATT = ["00:00:00:00:01:05", "00:00:00:00:01:06"]
SHADE = ("#cfe2f7", "#fbf1c4", "#f8cccc")          # before attack, filling, full

s = pd.read_csv(f"{RUN}/switch_T1B_s11.csv")
m = pd.read_csv(f"{RUN}/switch_T1B_s11_macs.csv")
t_full = float(s[s.entries >= 0.98 * CAP].t.min())
t_end = float(s.t.max())
per = m.pivot_table(index="t", columns="mac", values="entries", aggfunc="sum").fillna(0)
normal = per.drop(columns=ATT, errors="ignore").max(axis=1)

plt.rcParams.update({"font.size": 10, "axes.spines.top": True, "axes.spines.right": True})
fig, axs = plt.subplots(1, 2, figsize=(11, 3.9))


def states(ax, lo):
    for (a, b), c in zip(((0, T_ATT), (T_ATT, t_full), (t_full, t_end)), SHADE):
        ax.axvspan(a, b, ymin=0, ymax=1, color=c, lw=0)
    for x in (T_ATT, t_full):
        ax.axvline(x, color="black", lw=1.1)
    ax.set_xlim(0, t_end)
    ax.set_xlabel("Time(s)")


states(axs[0], 0)
axs[0].plot(s.t, s.entries, color="black", lw=1.0)
for r, lab in ((RHO1, "TH1"), (RHO2, "TH2")):
    axs[0].axhline(r * CAP, color="#c0392b", lw=1.0, ls="--")
    axs[0].text(4, r * CAP + 40, f"{lab} = {int(r * 100)} %", color="#c0392b", fontsize=9)
axs[0].set_ylim(0, CAP * 1.07)
axs[0].set_ylabel("FN (entries in the table)")

states(axs[1], 0)
for mac, ls, lab in ((ATT[0], "-", "attacker 1"), (ATT[1], (0, (4, 2)), "attacker 2")):
    if mac in per:
        axs[1].plot(per.index, per[mac], color="black", lw=1.0, ls=ls, label=lab)
axs[1].plot(normal.index, normal, color="#2a6db0", lw=1.0, label="busiest normal host")
axs[1].axhline(X, color="#c0392b", lw=1.0, ls="--")
axs[1].text(4, X + 30, f"X = {X:.0f}", color="#c0392b", fontsize=9)
axs[1].set_ylabel("entries held by one host")
axs[1].legend(loc="upper left", fontsize=8.5, frameon=False, bbox_to_anchor=(0.0, 0.93))
axs[1].set_ylim(0, max(per[ATT].max().max(), X) * 1.12)

for ax, cap in zip(axs, ("(a) Distribution of FN before and after the attack.",
                         "(b) Entries per host before and after the attack.")):
    ax.text(0.5, -0.27, cap, transform=ax.transAxes, ha="center", va="top", fontsize=12)
fig.tight_layout(w_pad=3)
os.makedirs("results/paper_figs/v6", exist_ok=True)
for ext in ("png", "pdf"):
    fig.savefig(f"results/paper_figs/v6/fig17_states_{V}.{ext}", dpi=200, bbox_inches="tight")
print(f"fig17_states_{V}: attack at {T_ATT:.0f} s, table full at {t_full:.0f} s; "
      f"attackers max {per[ATT].max().round().to_dict()}, busiest normal {normal.max():.0f}, X {X:.0f}")
