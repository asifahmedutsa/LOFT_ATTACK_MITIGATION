"""Builds the FEVER architecture and the testbed topology in the plain style of the related papers:
  docs/fever_architecture.{png,pdf}  federated training of the shared detector, and the detection and
                                     mitigation modules each controller runs
  docs/fever_topology.{png,pdf}      the testbed network (testbed/run_testbed.py, build_tree): Ryu
                                     controller, core switch S1 to the server, access switches S2 and S3
Values match results/v21/exported/ens_config_v5.json and testbed/run_testbed.py.

    ~/.venvs/loft/bin/python docs/build_fever_figs.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 10})
K, GREY = "#000000", "#9a9a9a"


def rect(ax, cx, cy, w, h, text, bold=False, fs=10, fc="white", ls="-"):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc=fc, ec=K, lw=0.9, ls=ls))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal", linespacing=1.15)


def arrow(ax, x0, y0, x1, y1, both=False):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", color=K, lw=1.0, mutation_scale=10))


def module(ax, x0, y0, w, h, title):
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=1.4", fc="none", ec=GREY,
                                lw=1.2, ls=(0, (5, 3))))
    ax.text(x0 + w / 2, y0 + 2.2, title, ha="center", va="center", fontsize=12, weight="bold")


# ------------------------------------------------------------------ architecture
fig = plt.figure(figsize=(10, 8.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 84)
ax.axis("off")


def line(ax, pts):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=K, lw=1.0)


ax.add_patch(FancyBboxPatch((4, 77), 92, 4.6, boxstyle="round,pad=0,rounding_size=0.8", fc="white", ec=K, lw=1.0))
ax.text(50, 79.3, "SDN Switch", ha="center", va="center", fontsize=14, weight="bold")
module(ax, 3, 31, 45, 43, "Attack Detection")
module(ax, 52, 31, 45, 43, "Attack Mitigation")
DX, MX = 25.5, 74.5
for y, t in ((67, "Flow Stats Polling (1 s)"), (59, "Occupancy > TH1 (70 %)"),
             (51, "Feature Calculating\n(changed entries)"), (43, "Federated Scoring")):
    rect(ax, DX, y, 26, 5.4, t, bold=True)
for y0, y1 in ((64.3, 61.7), (56.3, 53.7), (48.3, 45.7)):
    arrow(ax, DX, y0, DX, y1)
arrow(ax, DX, 77, DX, 69.7)
for y, t in ((43, "Flow Rule Eviction"), (51, "Host Blocking (rule A)\noutlier evictions"),
             (59, "Volume Blocking (rule B)\nentries > X, occupancy > TH2"), (67, "Fair-Share Trimming per Port\noccupancy > TH2")):
    rect(ax, MX, y, 30, 5.4, t, bold=True)
for y0, y1 in ((45.7, 48.3), (53.7, 56.3), (61.7, 64.3)):
    arrow(ax, MX, y0, MX, y1)
arrow(ax, MX, 69.7, MX, 77)
arrow(ax, DX + 13, 43, MX - 15, 43)
ax.text(50, 44.0, "score > τ", ha="center", fontsize=9.5, style="italic")

module(ax, 3, 3, 94, 24, "")
ax.text(50, 24.6, "Federated Training", ha="center", va="center", fontsize=12, weight="bold")
rect(ax, DX, 13.5, 26, 9, "Shared Detector\n3 CatBoost models\n(τ and X set on local\nbenign traffic)", bold=False, fs=9.5)
for i, (d, seen) in enumerate((("D1", "A1, A4"), ("D2", "A2, A5"), ("D3", "A3, A7"))):
    x = 56 + i * 15
    rect(ax, x, 16.5, 13, 7, f"Controller {d}\nlocal CatBoost\n(benign, {seen})", fs=9)
    line(ax, [(x, 13), (x, 9)])
line(ax, [(86, 9), (56, 9)])
arrow(ax, 56, 9, DX + 13, 9)
ax.text(47.5, 9.8, "model sharing", ha="center", fontsize=9.5, style="italic")
arrow(ax, DX - 9, 18, DX - 9, 40.3)
for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_architecture.{ext}", dpi=200, facecolor="white")
plt.close(fig)


# ------------------------------------------------------------------ topology
def computer(ax, cx, cy, col, label):
    ax.add_patch(Rectangle((cx - 2.6, cy - 0.6), 5.2, 3.6, fc="white", ec=col, lw=1.3))
    ax.add_patch(Rectangle((cx - 2.0, cy - 0.05), 4.0, 2.5, fc=col, ec=col, lw=0.6, alpha=0.35))
    ax.add_patch(Rectangle((cx - 0.5, cy - 1.6), 1.0, 1.0, fc=col, ec=col))
    ax.add_patch(Rectangle((cx - 2.0, cy - 2.0), 4.0, 0.5, fc=col, ec=col))
    ax.text(cx, cy - 3.3, label, ha="center", va="top", fontsize=10, weight="bold")


def switch(ax, cx, cy, label):
    ax.add_patch(Rectangle((cx - 3.4, cy - 1.3), 6.8, 2.6, fc="#cfe0f3", ec="#2f5597", lw=1.2))
    for k in range(5):
        ax.add_patch(Rectangle((cx - 2.6 + k * 1.15, cy - 0.35), 0.6, 0.7, fc="#2f5597", ec="none"))
    ax.text(cx - 4.2, cy, label, ha="right", va="center", fontsize=10.5, weight="bold")


BLUE, RED, GREEN = "#2f6fd0", "#e04040", "#8ca43a"
fig = plt.figure(figsize=(9.5, 6.2))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 95)
ax.set_ylim(0, 62)
ax.axis("off")
S1, S2, S3, C, SRV = (47, 36), (24, 22), (70, 22), (47, 53), (82, 36)
for sw in (S1, S2, S3):
    ax.plot([C[0], sw[0]], [C[1] - 3, sw[1] + 1.3], color=GREEN, lw=1.2, ls=(0, (4, 3)), zorder=0)
ax.plot([S1[0], S2[0]], [S1[1], S2[1]], color=RED, lw=1.6, zorder=0)
ax.plot([S1[0], S3[0]], [S1[1], S3[1]], color=RED, lw=1.6, zorder=0)
ax.plot([S1[0], SRV[0]], [S1[1], SRV[1]], color=BLUE, lw=1.4, zorder=0)
hosts2 = [(9, 7, "#3060c0", "User1"), (20, 7, "#3060c0", "User2"), (31, 7, "#e04040", "Attacker1")]
hosts3 = [(59, 7, "#3060c0", "User3"), (70, 7, "#3060c0", "User4"), (81, 7, "#e04040", "Attacker2")]
for sw, hs in ((S2, hosts2), (S3, hosts3)):
    for x, y, col, lab in hs:
        ax.plot([sw[0], x], [sw[1] - 1.3, y + 3.0], color=BLUE, lw=1.4, zorder=0)
        computer(ax, x, y, col, lab)
switch(ax, *S1, "S1")
switch(ax, *S2, "S2")
switch(ax, *S3, "S3")
ax.add_patch(Rectangle((C[0] - 2.2, C[1] - 3), 4.4, 6.2, fc="#d6e3f5", ec="#2f5597", lw=1.2))
for k in range(4):
    ax.plot([C[0] - 1.4, C[0] + 1.4], [C[1] + 1.8 - k * 1.1] * 2, color="#2f5597", lw=0.9)
ax.text(C[0], C[1] + 4.6, "SDN Controller (Ryu, FEVER)", ha="center", fontsize=11.5, weight="bold")
ax.add_patch(Rectangle((SRV[0] - 2.2, SRV[1] - 3), 4.4, 6.2, fc="#d9d2e9", ec="#5b4a9b", lw=1.2))
for k in range(4):
    ax.plot([SRV[0] - 1.4, SRV[0] + 1.4], [SRV[1] + 1.8 - k * 1.1] * 2, color="#5b4a9b", lw=0.9)
ax.text(SRV[0], SRV[1] - 4.2, "Server", ha="center", va="top", fontsize=10.5, weight="bold")
lx, ly = 66, 57
for i, (col, ls, lab) in enumerate(((BLUE, "-", "1000 Mbps 2 ms"), (RED, "-", "250 Mbps 15 ms"),
                                    (GREEN, (0, (4, 3)), "OpenFlow 1.3 control channel"))):
    ax.plot([lx, lx + 6], [ly - i * 2.8] * 2, color=col, lw=1.5, ls=ls)
    ax.text(lx + 7, ly - i * 2.8, lab, va="center", fontsize=10)
ax.text(3, 58, "Flow table: 3,500 entries\nIdle timeout: 10 s", fontsize=10, va="top")
for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_topology.{ext}", dpi=200, facecolor="white")
print("wrote docs/fever_architecture.png and docs/fever_topology.png")
