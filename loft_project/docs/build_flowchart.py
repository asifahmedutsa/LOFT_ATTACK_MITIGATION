"""Builds docs/fedvolguard_flowchart.{png,pdf}: the framework of FedVol-Guard (EnsGuard v5) as a
plain journal-style flowchart, in the layout used by the related papers (detection module on the
left, mitigation module on the right, the switch on top). Values match
results/v21/exported/ens_config_v5.json.

    ~/.venvs/loft/bin/python docs/build_flowchart.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 11})
K, GREY, RED = "#000000", "#9a9a9a", "#d23c3c"

fig = plt.figure(figsize=(10, 6.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 64)
ax.axis("off")


def rect(cx, cy, text, w=19, h=5.2, bold=True):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc="white", ec=K, lw=1.0))
    ax.text(cx, cy, text, ha="center", va="center", weight="bold" if bold else "normal",
            fontsize=10.5, linespacing=1.15)


def diamond(cx, cy, parts, w=21, h=6.4):
    ax.add_patch(Polygon([(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)],
                         closed=True, fc="white", ec=K, lw=1.0))
    # parts: [(text, colour), ...] set as one centred line
    fig.canvas.draw()
    inv = ax.transData.inverted()
    ts, widths = [], []
    for p, c in parts:
        t = ax.text(0, cy, p, ha="left", va="center", fontsize=10, weight="bold", color=c)
        bb = t.get_window_extent(renderer=fig.canvas.get_renderer()).transformed(inv)
        ts.append(t)
        widths.append(bb.x1 - bb.x0)
    x = cx - sum(widths) / 2
    for t, wd in zip(ts, widths):
        t.set_x(x)
        x += wd


def line(pts, arrow=True):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1] + (xs[-1],), ys, color=K, lw=1.0, solid_capstyle="butt")
    if arrow:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        ax.annotate("", xy=(x1, y1), xytext=(x0 + (x1 - x0) * 0.9, y0 + (y1 - y0) * 0.9),
                    arrowprops=dict(arrowstyle="-|>", color=K, lw=1.0, mutation_scale=11))


def label(x, y, t, **kw):
    ax.text(x, y, t, fontsize=9.5, **kw)


def module(x0, x1, title):
    ax.add_patch(FancyBboxPatch((x0, 3), x1 - x0, 51.5, boxstyle="round,pad=0,rounding_size=1.6",
                                fc="none", ec=GREY, lw=1.3, ls=(0, (5, 3))))
    ax.text((x0 + x1) / 2, 6.2, title, ha="center", va="center", fontsize=13.5, weight="bold")


# switch bar
ax.add_patch(FancyBboxPatch((4, 57.5), 92, 4.6, boxstyle="round,pad=0,rounding_size=0.8", fc="white", ec=K, lw=1.0))
ax.text(50, 59.8, "SDN Switch", ha="center", va="center", fontsize=14, weight="bold")

module(2.5, 48.5, "Attack Detection")
module(51.5, 97.5, "Attack Mitigation")

# ---- detection
rect(18, 49.5, "Flow Stats Polling (1 s)")
diamond(18, 41.5, [("Occupancy > ", K), ("TH1", RED)])
rect(18, 33, "Feature Calculating")
rect(18, 24, "Federated Scoring")
rect(18, 13.5, "Shared CatBoost Models\n(Controllers D1, D2, D3)", w=22, h=6.4, bold=False)
ax.text(19.2, 18.7, "model sharing", ha="left", va="center", fontsize=9.5, color="#555555", style="italic")

line([(18, 57.5), (18, 52.1)])
line([(18, 46.9), (18, 44.7)])
line([(18, 38.3), (18, 35.6)])
label(19, 36.4, "Yes")
line([(7.5, 41.5), (5, 41.5), (5, 49.5), (8.5, 49.5)])
label(5.4, 42.6, "No")
line([(18, 30.4), (18, 26.6)])
line([(18, 16.7), (18, 21.4)])

# ---- mitigation
rect(64, 24, "Flow Rule Eviction")
diamond(64, 34, [("Outlier Host?", K)], w=19)
diamond(64, 44, [("Occupancy > ", K), ("TH2", RED)])
rect(85.5, 34, "Host Blocking", w=15)
rect(85.5, 44, "Volume Blocking and\nFair-Share Trimming", w=15, h=6.4, bold=True)

line([(27.5, 24), (54.5, 24)])  # entries scoring above tau
ax.text(41, 25.2, "Score > ", ha="right", fontsize=9.5)
ax.text(41, 25.2, "τ", ha="left", fontsize=9.5, color=RED)
line([(64, 27.2), (64, 30.8)])
line([(73.5, 34), (78, 34)])
label(74.2, 35, "Yes")
line([(64, 37.2), (64, 40.8)])
label(65, 38.4, "No")
line([(74.5, 44), (78, 44)])
label(74.6, 45, "Yes")
# both blocking boxes act on the switch
line([(93, 34), (95, 34), (95, 44)], arrow=False)
line([(93, 44), (95, 44), (95, 57.5)])
# no further action: next poll
line([(53.5, 44), (40, 44), (40, 49.5), (27.5, 49.5)])
label(44, 45, "No")
ax.text(40.6, 51.3, "next poll", fontsize=9.5, style="italic", color="#555555")

for ext in ("png", "pdf"):
    fig.savefig(f"docs/fedvolguard_flowchart.{ext}", dpi=200, facecolor="white")
print("docs/fedvolguard_flowchart.png")
