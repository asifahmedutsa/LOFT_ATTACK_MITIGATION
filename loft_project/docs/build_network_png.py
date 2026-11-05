"""Builds docs/ensguard_network.png: the deployment view of FL-EnsGuard, drawn as a network
(SDN controllers, Open vSwitch switches, hosts, attackers, server). Topology as run_testbed.py
--topo tree3: per domain k, controller c_k, core s_k1 to the server, edge s_k2 (hosts 1, 2 and
attacker 5) and s_k3 (hosts 3, 4 and attacker 6)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

INK, MUTED, BG = "#1f2933", "#52606d", "#fbfbf8"
CTRL, CTRL_L = "#534ab7", "#e4e1fb"
SW, SW_L = "#1d5fa8", "#cfe2f7"
HOST, HOST_L = "#3e4c59", "#e4e7eb"
ATK, ATK_L = "#b42318", "#fde2df"
SRV, SRV_L = "#0f6e56", "#d3efe6"
FED, FED_L = "#854f0b", "#f8e7c6"

fig = plt.figure(figsize=(18, 11), dpi=150)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 180)
ax.set_ylim(0, 110)
ax.axis("off")
fig.patch.set_facecolor(BG)


def rbox(x, y, w, h, fc, ec, r=1.2, lw=1.4, z=2, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc,
                                ec=ec, lw=lw, zorder=z, linestyle=ls))


def line(x0, y0, x1, y1, col=MUTED, lw=1.6, ls="-", z=1):
    ax.plot([x0, x1], [y0, y1], color=col, lw=lw, ls=ls, zorder=z, solid_capstyle="round")


def arrow(x0, y0, x1, y1, col, lw=1.6, ls="-", style="-|>", z=3, rad=0.0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=13,
                                 color=col, lw=lw, linestyle=ls, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}"))


def computer(cx, cy, label, attacker=False):
    """Monitor + stand + keyboard; cx, cy = centre of the screen."""
    ec, fc = (ATK, ATK_L) if attacker else (HOST, HOST_L)
    rbox(cx - 3.2, cy - 2.2, 6.4, 4.6, fc, ec, r=0.4, lw=1.5, z=4)
    ax.add_patch(Rectangle((cx - 2.6, cy - 1.6), 5.2, 3.4, fc="white", ec=ec, lw=0.6, zorder=5))
    ax.add_patch(Polygon([(cx - 0.6, cy - 2.2), (cx + 0.6, cy - 2.2), (cx + 1.0, cy - 3.3),
                          (cx - 1.0, cy - 3.3)], fc=ec, ec=ec, zorder=4))
    rbox(cx - 2.8, cy - 4.1, 5.6, 0.8, fc, ec, r=0.2, lw=1.0, z=4)
    if attacker:
        ax.text(cx, cy + 0.1, "☠", ha="center", va="center", fontsize=13, color=ATK, zorder=6)
    else:
        for k in range(3):
            line(cx - 1.8, cy + 0.9 - k * 0.9, cx + (1.8 if k < 2 else 0.4), cy + 0.9 - k * 0.9,
                 col="#9aa5b1", lw=1.2, z=6)
    ax.text(cx, cy - 5.4, label, ha="center", va="center", fontsize=8.6,
            color=ATK if attacker else INK, weight="bold" if attacker else "normal", zorder=6)


def switch(cx, cy, label, sub):
    """Flat switch box with the four crossing arrows of the usual network-switch icon."""
    w, h = 12, 4.4
    rbox(cx - w / 2, cy - h / 2, w, h, SW_L, SW, r=0.9, lw=1.8, z=4)
    for dy, d in ((0.8, 1), (-0.8, -1)):
        arrow(cx - 3.6 * d, cy + dy, cx + 3.6 * d, cy + dy, SW, lw=1.4, z=5)
    ax.text(cx + w / 2 + 0.8, cy + 0.7, label, ha="left", va="center", fontsize=10, weight="bold",
            color=SW, zorder=6)
    ax.text(cx + w / 2 + 0.8, cy - 1.0, sub, ha="left", va="center", fontsize=7.6, color=MUTED,
            zorder=6)


def server_tower(cx, cy, label, col, fcol, w=5.2, h=7.5, lines=4):
    rbox(cx - w / 2, cy - h / 2, w, h, fcol, col, r=0.5, lw=1.6, z=4)
    for k in range(lines):
        yy = cy + h / 2 - 1.4 - k * 1.3
        line(cx - w / 2 + 0.8, yy, cx + w / 2 - 1.6, yy, col=col, lw=1.4, z=5)
        ax.add_patch(Ellipse((cx + w / 2 - 0.9, yy), 0.45, 0.45, fc=col, ec=col, zorder=5))
    ax.text(cx, cy - h / 2 - 1.3, label, ha="center", va="center", fontsize=8.8, color=INK, zorder=6)


def cloud(cx, cy, s=1.0):
    for dx, dy, rw, rh in ((-6, -0.6, 9, 6.5), (0, 1.8, 11, 8), (6.5, 0, 9, 6.6), (2, -1.8, 14, 5.4),
                           (-3, -1.8, 12, 5.2)):
        ax.add_patch(Ellipse((cx + dx * s, cy + dy * s), rw * s, rh * s, fc=FED_L, ec="none", zorder=2))
    for dx, dy, rw, rh in ((-6, -0.6, 9, 6.5), (0, 1.8, 11, 8), (6.5, 0, 9, 6.6)):
        ax.add_patch(Ellipse((cx + dx * s, cy + dy * s), rw * s, rh * s, fc="none", ec=FED, lw=1.3,
                             zorder=1))


# ---------- title ----------
ax.text(90, 106.5, "FL-EnsGuard deployment: three SDN domains, one federated detector",
        ha="center", va="center", fontsize=18, weight="bold", color=INK)
ax.text(90, 103, "Each domain: a Ryu controller, three Open vSwitch switches in a tree, one server, "
        "four benign hosts and two low-rate attackers", ha="center", va="center", fontsize=11,
        color=MUTED)

# ---------- federation ----------
cloud(90, 93.2)
ax.text(90, 95.2, "Federated model sharing", ha="center", va="center", fontsize=11.5,
        weight="bold", color=FED, zorder=3)
ax.text(90, 91.6, "RF + CatBoost from D1, D2, D3 → shared ensemble\n(models only; flow data stays "
        "in its domain)", ha="center", va="center", fontsize=8.6, color=INK, zorder=3,
        linespacing=1.3)

XS = (30, 90, 150)
for k, cx in enumerate(XS, start=1):
    # domain panel
    rbox(cx - 28, 2.5, 56, 80, "#ffffff", "#c9ccd1", r=2.0, lw=1.2, z=0, ls=(0, (5, 3)))
    ax.text(cx - 26, 80.2, f"Domain D{k}", fontsize=12.5, weight="bold", color=INK, va="center")

    # controller
    cy_c = 72
    server_tower(cx - 9, cy_c, "", CTRL, CTRL_L, w=6, h=8.5, lines=5)
    rbox(cx - 4.5, cy_c - 5.2, 30, 10.6, CTRL_L, CTRL, r=1.0, lw=1.4, z=3)
    ax.text(cx + 10.5, cy_c + 3.4, f"SDN controller c{k} (Ryu)", ha="center", va="center",
            fontsize=9.8, weight="bold", color=CTRL, zorder=4)
    ax.text(cx + 10.5, cy_c - 1.0, "EnsGuard app, every 1 s poll:\nscore → evict ≥ τ → block\n"
            "outlier host → PortGuard", ha="center", va="center", fontsize=8.2, color=INK, zorder=4,
            linespacing=1.3)
    # up to federation
    arrow(cx + (6 if k == 1 else -6 if k == 3 else 0), cy_c + 5.6,
          90 + (-11 if k == 1 else 11 if k == 3 else 0), 88.6 if k != 2 else 88.4, FED, lw=1.6,
          style="<|-|>", rad=(-0.15 if k == 1 else 0.15 if k == 3 else 0))

    # switches
    core, e1, e2 = (cx - 4, 52), (cx - 15, 33), (cx + 9, 33)
    switch(*core, f"s{k}1", "core OVS")
    switch(*e1, f"s{k}2", "edge OVS")
    switch(*e2, f"s{k}3", "edge OVS")
    for (sx, sy), ox, oy in ((core, cx - 9, cy_c - 4.4), (e1, cx - 9, cy_c - 4.4),
                             (e2, cx + 9, cy_c - 5.2)):
        line(ox, oy, sx, sy + 2.2, col=CTRL, lw=1.2, ls=(0, (4, 3)), z=1)
    ax.text(cx - 14.5, 61.6, "OpenFlow 1.3", fontsize=7.6, color=CTRL, rotation=0, va="center")
    for ex, ey in (e1, e2):
        line(core[0], core[1] - 2.2, ex, ey + 2.2, col=SW, lw=2.4, z=1)
    ax.text(core[0] + 0.6, 40.5, "250 Mbit/s\n15 ms", fontsize=7.2, color=MUTED, va="center",
            ha="center", linespacing=1.2)

    # server on the core
    sx = cx + 17
    server_tower(sx, 54.8, f"server srv{k}", SRV, SRV_L, w=4.6, h=6.6, lines=3)
    line(core[0] + 6, core[1], sx - 2.3, 53.5, col=SW, lw=1.6, z=1)

    # hosts: s_k2 has h1, h2, attacker h5; s_k3 has h3, h4, attacker h6
    for (ex, ey), hosts in ((e1, ((1, False), (2, False), (5, True))),
                            (e2, ((3, False), (4, False), (6, True)))):
        for j, (hid, atk) in enumerate(hosts):
            hx, hy = ex - 7 + j * 7, 15.5
            line(ex, ey - 2.2, hx, hy + 2.4, col=ATK if atk else HOST, lw=1.2,
                 ls=(0, (2, 2)) if atk else "-", z=1)
            computer(hx, hy, f"d{k}h{hid}" + (" attacker" if atk else ""), attacker=atk)

# Callouts on domain D1
ax.text(30, 6.2, "attackers refresh many 5-tuple rules just below\nthe idle timeout (10 s) to fill "
        "every table", ha="center", va="center", fontsize=7.8, color=ATK, linespacing=1.25)

# ---------- legend ----------
lx, ly = 3, 99.5
items = [(CTRL, "SDN controller (Ryu + EnsGuard)"), (SW, "Open vSwitch (3500-entry table)"),
         (HOST, "benign host"), (ATK, "attacker (low-rate flow-table overflow)"),
         (SRV, "server"), (FED, "federated model sharing")]
for i, (c, t) in enumerate(items):
    yy = ly - i * 2.4
    ax.add_patch(Rectangle((lx, yy - 0.7), 1.6, 1.4, fc=c, ec=c, zorder=3))
    ax.text(lx + 2.4, yy, t, fontsize=8.4, color=INK, va="center")
line(150, 99.5, 154, 99.5, col=CTRL, lw=1.2, ls=(0, (4, 3)))
ax.text(155, 99.5, "OpenFlow control channel", fontsize=8.4, color=INK, va="center")
line(150, 97.1, 154, 97.1, col=SW, lw=2.4)
ax.text(155, 97.1, "switch link", fontsize=8.4, color=INK, va="center")
line(150, 94.7, 154, 94.7, col=ATK, lw=1.2, ls=(0, (2, 2)))
ax.text(155, 94.7, "attacker link", fontsize=8.4, color=INK, va="center")

fig.savefig("docs/ensguard_network.png", dpi=150, facecolor=BG)
print("docs/ensguard_network.png")
