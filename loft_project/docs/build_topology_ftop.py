"""Builds docs/fever_testbed_topology.{png,pdf}: the testbed network in the style of FTOP's Fig. 9
(grey device icons, bandwidth and delay on every link, dashed red control links). Links and hosts
follow testbed/run_testbed.py (build_tree).

    ~/.venvs/loft/bin/python docs/build_topology_ftop.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 10})
G1, G2, G3, K = "#e6e6e6", "#b5b5b5", "#6e6e6e", "#000000"
CYAN, RED = "#1aa0d8", "#e03030"

fig = plt.figure(figsize=(8.6, 6.6))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 86)
ax.set_ylim(0, 66)
ax.axis("off")


def tower(cx, cy, s=1.0):
    """Grey tower server (controller, server)."""
    ax.add_patch(Polygon([(cx - 2.2 * s, cy - 3.5 * s), (cx + 1.6 * s, cy - 3.5 * s), (cx + 1.6 * s, cy + 3.2 * s),
                          (cx - 2.2 * s, cy + 3.2 * s)], fc=G1, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx + 1.6 * s, cy - 3.5 * s), (cx + 2.6 * s, cy - 2.9 * s), (cx + 2.6 * s, cy + 3.8 * s),
                          (cx + 1.6 * s, cy + 3.2 * s)], fc=G2, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx - 2.2 * s, cy + 3.2 * s), (cx + 1.6 * s, cy + 3.2 * s), (cx + 2.6 * s, cy + 3.8 * s),
                          (cx - 1.2 * s, cy + 3.8 * s)], fc="#f4f4f4", ec=G3, lw=0.9, zorder=3))
    for k in range(3):
        ax.plot([cx - 1.6 * s, cx + 1.0 * s], [cy + (1.8 - k * 0.8) * s] * 2, color=G3, lw=0.7, zorder=4)
    ax.add_patch(Circle((cx - 0.3 * s, cy - 2.2 * s), 0.35 * s, fc=G3, ec="none", zorder=4))


def computer(cx, cy, s=1.0):
    """Grey desktop: monitor and keyboard."""
    ax.add_patch(Polygon([(cx - 2.3 * s, cy - 0.6 * s), (cx + 2.3 * s, cy - 0.6 * s), (cx + 2.3 * s, cy + 3.0 * s),
                          (cx - 2.3 * s, cy + 3.0 * s)], fc=G2, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Rectangle((cx - 1.9 * s, cy - 0.25 * s), 3.8 * s, 2.9 * s, fc="#f7f7f7", ec=G3, lw=0.6, zorder=4))
    ax.add_patch(Polygon([(cx - 0.5 * s, cy - 0.6 * s), (cx + 0.5 * s, cy - 0.6 * s), (cx + 0.8 * s, cy - 1.3 * s),
                          (cx - 0.8 * s, cy - 1.3 * s)], fc=G3, ec=G3, zorder=3))
    ax.add_patch(Polygon([(cx - 2.6 * s, cy - 1.5 * s), (cx + 2.2 * s, cy - 1.5 * s), (cx + 2.8 * s, cy - 2.2 * s),
                          (cx - 2.0 * s, cy - 2.2 * s)], fc=G1, ec=G3, lw=0.8, zorder=3))


def person(cx, cy, col):
    ax.add_patch(Circle((cx, cy + 1.6), 0.9, fc=col, ec=K, lw=0.6, zorder=5))
    ax.add_patch(Wedge((cx, cy - 0.2), 1.6, 0, 180, fc=col, ec=K, lw=0.6, zorder=5))


def switch(cx, cy):
    ax.add_patch(Polygon([(cx - 3.0, cy - 0.6), (cx + 2.2, cy - 0.6), (cx + 3.4, cy + 0.6), (cx - 1.8, cy + 0.6)],
                         fc=G1, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx - 3.0, cy - 0.6), (cx + 2.2, cy - 0.6), (cx + 2.2, cy - 1.5), (cx - 3.0, cy - 1.5)],
                         fc=G2, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx + 2.2, cy - 0.6), (cx + 3.4, cy + 0.6), (cx + 3.4, cy - 0.3), (cx + 2.2, cy - 1.5)],
                         fc=G3, ec=G3, lw=0.9, zorder=3))
    for k in range(5):
        ax.add_patch(Rectangle((cx - 2.6 + k * 0.95, cy - 1.25), 0.5, 0.45, fc="#4a4a4a", ec="none", zorder=4))


def link(a, b, label=None, off=(0, 0), col=K, ls="-", lw=1.0):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=col, lw=lw, ls=ls, zorder=1)
    if label:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], label, ha="center", va="center",
                fontsize=9.5, zorder=6, bbox=dict(fc="white", ec="none", pad=0.6))


C, S1, S2, S3, SRV = (43, 57), (43, 39), (22, 26), (64, 26), (74, 44)
HOST, AH = "1Gbps\n2ms", "250Mbps\n15ms"
for sw in (S1, S2, S3):
    link((C[0], C[1] - 3.5), sw, col=RED, ls=(0, (5, 4)), lw=1.0)
link(S1, S2, AH, off=(3.0, -3.2))
link(S1, S3, AH, off=(-3.0, -3.2))
link(S1, SRV, HOST, off=(0, 2.4))
hosts = [(S2, (6, 9), "h1", None), (S2, (18, 7), "h2", None), (S2, (31, 8), "h5", "Attacker"),
         (S3, (55, 8), "h3", None), (S3, (68, 7), "h4", None), (S3, (80, 9), "h6", "Attacker")]
for sw, (x, y), name, role in hosts:
    link(sw, (x, y + 3.0), HOST if name in ("h1", "h4") else None, off=(-3.2, 0.6))
tower(*C, 1.15)
ax.text(C[0] + 4.4, C[1] + 1.5, "SDN controller\n(Ryu, FEVER)", ha="left", va="center", fontsize=10.5)
tower(*SRV, 1.0)
ax.text(SRV[0] + 3.6, SRV[1] - 0.5, "Server", ha="left", va="center", fontsize=10.5)
for sw, lab in ((S1, "S1"), (S2, "S2"), (S3, "S3")):
    switch(*sw)
    ax.text(sw[0] + (0 if lab == "S1" else (-4.6 if lab == "S2" else 4.8)), sw[1] - (3.4 if lab == "S1" else 0.3),
            lab, ha="center", va="center", fontsize=10.5, color=CYAN)
for sw, (x, y), name, role in hosts:
    computer(x, y)
    if role:
        person(x - 4.2, y - 0.6, "#e05050")
    ax.text(x - (2.1 if role else 0), y - 3.4, f"{name} ({role})" if role else name, ha="center", va="top", fontsize=10.5)
ax.text(2, 63, "Flow table: 3,500 entries\nIdle timeout: 10 s", fontsize=9.5, va="top")
for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_testbed_topology.{ext}", dpi=200, facecolor="white", bbox_inches="tight")
print("wrote docs/fever_testbed_topology.png")
