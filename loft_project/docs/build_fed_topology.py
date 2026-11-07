"""Builds docs/fever_federated_topology.{png,pdf}: the experiment network with the federation drawn
in, in the device-icon style of FTOP's topology figure. Three SDN domains (D1-D3) train local
models and exchange them with a federated server; the test domain (the Mininet testbed replaying
bigFlows) receives the shared detector. Every domain has the tree of testbed/run_testbed.py
(build_tree).

    ~/.venvs/loft/bin/python docs/build_fed_topology.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 10})
G1, G2, G3, K, GREY = "#e6e6e6", "#b5b5b5", "#6e6e6e", "#000000", "#9a9a9a"
CYAN, RED, UP, DOWN = "#1aa0d8", "#e03030", "#c0504d", "#2f6fd0"

fig = plt.figure(figsize=(14, 11.7))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 150)
ax.set_ylim(0, 125)
ax.axis("off")


def tower(cx, cy, s=1.0, fc=G1):
    ax.add_patch(Polygon([(cx - 2.2 * s, cy - 3.5 * s), (cx + 1.6 * s, cy - 3.5 * s), (cx + 1.6 * s, cy + 3.2 * s),
                          (cx - 2.2 * s, cy + 3.2 * s)], fc=fc, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx + 1.6 * s, cy - 3.5 * s), (cx + 2.6 * s, cy - 2.9 * s), (cx + 2.6 * s, cy + 3.8 * s),
                          (cx + 1.6 * s, cy + 3.2 * s)], fc=G2, ec=G3, lw=0.9, zorder=3))
    ax.add_patch(Polygon([(cx - 2.2 * s, cy + 3.2 * s), (cx + 1.6 * s, cy + 3.2 * s), (cx + 2.6 * s, cy + 3.8 * s),
                          (cx - 1.2 * s, cy + 3.8 * s)], fc="#f4f4f4", ec=G3, lw=0.9, zorder=3))
    for k in range(3):
        ax.plot([cx - 1.6 * s, cx + 1.0 * s], [cy + (1.8 - k * 0.8) * s] * 2, color=G3, lw=0.7, zorder=4)
    ax.add_patch(Circle((cx - 0.3 * s, cy - 2.2 * s), 0.35 * s, fc=G3, ec="none", zorder=4))


def computer(cx, cy, s, attacker=False):
    ax.add_patch(Rectangle((cx - 2.3 * s, cy - 0.6 * s), 4.6 * s, 3.6 * s, fc=G2, ec=G3, lw=0.8, zorder=3))
    ax.add_patch(Rectangle((cx - 1.9 * s, cy - 0.25 * s), 3.8 * s, 2.9 * s, fc="#f7f7f7", ec=G3, lw=0.5, zorder=4))
    ax.add_patch(Polygon([(cx - 0.5 * s, cy - 0.6 * s), (cx + 0.5 * s, cy - 0.6 * s), (cx + 0.8 * s, cy - 1.3 * s),
                          (cx - 0.8 * s, cy - 1.3 * s)], fc=G3, ec=G3, zorder=3))
    ax.add_patch(Polygon([(cx - 2.6 * s, cy - 1.5 * s), (cx + 2.2 * s, cy - 1.5 * s), (cx + 2.8 * s, cy - 2.2 * s),
                          (cx - 2.0 * s, cy - 2.2 * s)], fc=G1, ec=G3, lw=0.7, zorder=3))
    if attacker:
        px, py = cx - 3.9 * s, cy - 0.6 * s
        ax.add_patch(Circle((px, py + 1.6 * s), 0.9 * s, fc="#e05050", ec=K, lw=0.5, zorder=5))
        ax.add_patch(Wedge((px, py - 0.2 * s), 1.6 * s, 0, 180, fc="#e05050", ec=K, lw=0.5, zorder=5))


def switch(cx, cy, s):
    ax.add_patch(Polygon([(cx - 3.0 * s, cy - 0.6 * s), (cx + 2.2 * s, cy - 0.6 * s), (cx + 3.4 * s, cy + 0.6 * s),
                          (cx - 1.8 * s, cy + 0.6 * s)], fc=G1, ec=G3, lw=0.8, zorder=3))
    ax.add_patch(Polygon([(cx - 3.0 * s, cy - 0.6 * s), (cx + 2.2 * s, cy - 0.6 * s), (cx + 2.2 * s, cy - 1.5 * s),
                          (cx - 3.0 * s, cy - 1.5 * s)], fc=G2, ec=G3, lw=0.8, zorder=3))
    ax.add_patch(Polygon([(cx + 2.2 * s, cy - 0.6 * s), (cx + 3.4 * s, cy + 0.6 * s), (cx + 3.4 * s, cy - 0.3 * s),
                          (cx + 2.2 * s, cy - 1.5 * s)], fc=G3, ec=G3, lw=0.8, zorder=3))
    for k in range(5):
        ax.add_patch(Rectangle((cx + (-2.6 + k * 0.95) * s, cy - 1.25 * s), 0.5 * s, 0.45 * s, fc="#4a4a4a", ec="none",
                               zorder=4))


def domain(ox, oy, title, sub, s=0.62, labels=True):
    """One SDN domain (box ox..ox+46, oy..oy+42); returns the controller position."""
    P = lambda x, y: (ox + x, oy + y)  # noqa: E731
    C, S1, S2, S3, SRV = P(23, 31), P(23, 21), P(11, 12.5), P(35, 12.5), P(40, 23)
    for sw in (S1, S2, S3):
        ax.plot([C[0], sw[0]], [C[1] - 2.2, sw[1]], color=RED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    for a, b in ((S1, S2), (S1, S3), (S1, SRV)):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=K, lw=0.9, zorder=1)
    hosts = [(S2, P(3, 3), False, "h1"), (S2, P(10, 2.5), False, "h2"), (S2, P(18.5, 3), True, "h5"),
             (S3, P(28, 3), False, "h3"), (S3, P(35, 2.5), False, "h4"), (S3, P(43, 3), True, "h6")]
    for sw, (x, y), att, name in hosts:
        ax.plot([sw[0], x], [sw[1], y + 1.9], color=K, lw=0.9, zorder=1)
    tower(*C, s)
    tower(*SRV, s * 0.85)
    for sw in (S1, S2, S3):
        switch(*sw, s)
    for sw, (x, y), att, name in hosts:
        computer(x, y, s, att)
        ax.text(x, y - 1.8, name, ha="center", va="top", fontsize=8.5)
    ax.text(C[0] + 2.6, C[1] + 0.4, "Controller", ha="left", va="center", fontsize=9.5)
    ax.text(SRV[0], SRV[1] - 3.0, "Server", ha="center", va="top", fontsize=8.5)
    for sw, lab, dx in ((S1, "S1", -3.4), (S2, "S2", -3.6), (S3, "S3", 3.6)):
        ax.text(sw[0] + dx, sw[1] + 0.2, lab, ha="center", va="center", fontsize=9, color=CYAN)
    ax.add_patch(FancyBboxPatch((ox - 1, oy - 1.5), 48, 43, boxstyle="round,pad=0,rounding_size=1.2", fc="none",
                                ec=GREY, lw=1.1, ls=(0, (5, 3))))
    ax.text(ox + 1, oy + 39.6, title, ha="left", va="center", fontsize=11, weight="bold")
    ax.text(ox + 1, oy + 37.0, sub, ha="left", va="center", fontsize=9, style="italic")
    return C


FS = (75, 60)
tower(*FS, 1.25, fc="#f6ead7")
ax.text(FS[0] + 4.6, FS[1] + 1.2, "Federated server", ha="left", va="center", fontsize=12, weight="bold")
ax.text(FS[0] + 4.6, FS[1] - 2.2, "aggregates the local models\ninto the shared detector", ha="left", va="center",
        fontsize=9.5)
tops = []
for i, (d, kind, seen) in enumerate((("D1", "enterprise", "A1, A4"), ("D2", "IoT", "A2, A5"), ("D3", "cloud", "A3, A7"))):
    ox = 3 + i * 49
    domain(ox, 77, f"SDN domain {d} ({kind})", f"local model trained on benign + {seen}")
    bx = ox + 23
    sg = -1 if i < 2 else 1          # the arrow nearer the server sits on the inner side, so the pair never crosses
    ax.annotate("", xy=(FS[0] + sg * 1.5 + (bx - 75) * 0.06, FS[1] + 4.6), xytext=(bx + sg * 2.5, 75.5),
                arrowprops=dict(arrowstyle="-|>", color=UP, lw=1.6, mutation_scale=12))
    ax.annotate("", xy=(bx - sg * 2.5, 75.5), xytext=(FS[0] - sg * 1.5 + (bx - 75) * 0.06, FS[1] + 4.6),
                arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=1.6, ls="--", mutation_scale=12))
domain(52, 4, "Test domain (Mininet testbed)", "bigFlows replayed; FEVER uses the shared detector")
ax.annotate("", xy=(75, 46.5), xytext=(FS[0], FS[1] - 4.4),
            arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=1.6, ls="--", mutation_scale=12))

lx, ly = 106, 44
for i, (col, ls, lab) in enumerate(((UP, "-", "local model upload (no traffic data)"),
                                    (DOWN, (0, (4, 3)), "shared detector download"),
                                    (RED, (0, (4, 3)), "OpenFlow 1.3 control channel"))):
    ax.plot([lx, lx + 5], [ly - i * 3.0] * 2, color=col, lw=1.5, ls=ls)
    ax.text(lx + 6, ly - i * 3.0, lab, va="center", fontsize=10)
ax.text(lx, ly - 3 * 3.0 - 0.6, "Hosts and server: 1 Gbps, 2 ms\nS1 to S2/S3: 250 Mbps, 15 ms\n"
        "Flow tables: 3,500 entries, idle 10 s", va="top", fontsize=10)
for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_federated_topology.{ext}", dpi=200, facecolor="white", bbox_inches="tight")
print("wrote docs/fever_federated_topology.png")
