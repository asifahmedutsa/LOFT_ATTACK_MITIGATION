"""Builds docs/fever_working.{png,pdf}: "Working of proposed system" for FEVER, laid out like the
system figure of FTShield (offline phase on top, numbered steps, online detection and mitigation
below). Values match results/v21/exported/ens_config_v5.json.

    ~/.venvs/loft/bin/python docs/build_working_fig.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 10})
K = "#000000"
SALMON, SALMON_E = "#f4b183", "#c55a11"
BLUE, BLUE_E = "#8faadc", "#2f5597"
DIAM = "#4472c4"
RED, YEL = "#ff2b2b", "#ffff4d"
GREY = "#7f7f7f"

fig = plt.figure(figsize=(10, 6.6))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 66)
ax.axis("off")


def box(x, y, w, h, text, fc="white", ec=K, fs=9.5, lw=0.9, color=K, bold=False):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color,
            weight="bold" if bold else "normal", linespacing=1.15)


def num(x, y, n):
    ax.add_patch(Circle((x, y), 1.25, fc="#808080", ec="#404040", lw=0.6, zorder=5))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=8.5, color="white", zorder=6)


def arrow(x0, y0, x1, y1, label=None, lx=0, ly=0.8):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=K, lw=1.0, mutation_scale=10))
    if label:
        ax.text((x0 + x1) / 2 + lx, (y0 + y1) / 2 + ly, label, ha="center", fontsize=8.5)


def line(pts):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=K, lw=1.0)


# ---------------- phase 1: offline (top row)
top = [(2, "Flow-entry data of\ncontrollers D1, D2, D3"), (22, "Feature extraction\n(17 features)"),
       (42, "Local CatBoost\ntraining"), (62, "Model sharing\n(models, not data)"),
       (81, "Threshold calibration\n(τ, X) on benign traffic")]
for i, (x, t) in enumerate(top):
    box(x, 55.5, 16 if i < 4 else 17, 6.5, t, fc="#f2f2f2", ec=GREY, fs=9)
    num(x + 0.4, 55.5, i + 1)
    if i < 4:
        arrow(x + 16, 58.75, top[i + 1][0], 58.75)
ax.plot([2, 98], [52.2, 52.2], color=K, lw=1.0, ls=(0, (6, 4)))
arrow(89.5, 55.5, 89.5, 47.6)
ax.text(90.8, 50.3, "Deploy shared\nmodel, τ and X", fontsize=8.5, va="center")
num(88.0, 50.3, 6)

# ---------------- phase 2-3: online, in the controller
ax.add_patch(FancyBboxPatch((44.5, 30.5), 53, 17, boxstyle="round,pad=0,rounding_size=1.5",
                            fc="none", ec=K, lw=0.8, ls=(0, (4, 3))))
ax.text(71, 46.2, "Host check (every switch, every poll)", ha="center", fontsize=9)

box(3, 41, 17, 6, "Flow stats polling\n(every 1 s)", fc=SALMON, ec=SALMON_E)
num(3.4, 41, 7)
arrow(11.5, 41, 11.5, 37.6)
box(3, 31.6, 17, 6, "Occupancy check\n(≥ TH1 = 70 %)", fc=SALMON, ec=SALMON_E)
num(3.4, 31.6, 8)
arrow(11.5, 31.6, 11.5, 28.2)
box(3, 22.2, 17, 6, "Feature calculation\n(changed entries)", fc=SALMON, ec=SALMON_E)
num(3.4, 22.2, 9)

ax.add_patch(FancyBboxPatch((23, 20.6), 26, 9.2, boxstyle="round,pad=0,rounding_size=1.2",
                            fc="#fbe5d6", ec=SALMON_E, lw=0.9, ls=(0, (4, 3))))
box(24.2, 22, 11, 6.4, "Feature\nvectors", fc=BLUE, ec=BLUE_E)
box(36.6, 22, 11.2, 6.4, "Shared\nCatBoost\nmodels", fc=BLUE, ec=BLUE_E)
arrow(20, 25.2, 24.2, 25.2)
arrow(35.2, 25.2, 36.6, 25.2)
num(24.5, 20.6, 10)

# decision: malicious entry?
dx, dy = 59, 16
ax.add_patch(Polygon([(dx - 8, dy), (dx, dy + 5), (dx + 8, dy), (dx, dy - 5)], fc=DIAM, ec="#1f3864", lw=0.9))
ax.text(dx, dy, "Score ≥ τ ?", ha="center", va="center", fontsize=9.5, color="white")
line([(49, 25.2), (dx, 25.2)])
arrow(dx, 25.2, dx, dy + 5)
num(dx - 8.6, dy + 2.6, 11)
box(dx - 9, 3.2, 18, 5.2, "Keep entry", fc=YEL, ec="#7f6000")
arrow(dx, dy - 5, dx, 8.4, "no", lx=1.6, ly=0)
num(dx - 9 + 0.4, 3.2, 12)

box(70, 13.4, 15, 5.2, "Evict flow entry", fc=SALMON, ec=SALMON_E)
arrow(dx + 8, dy, 70, 16, "yes", ly=0.8)
num(70.4, 13.4, 13)

# host check table (inside the dashed region)
tx, ty = 46.5, 32.5
cols = [(0, 7.5, "Host"), (7.5, 9, "Entries\nheld"), (16.5, 10, "Evictions\nin 10 s")]
for x0, w, h in cols:
    box(tx + x0, ty + 7.6, w, 4.4, h, fc=DIAM, ec="#1f3864", fs=8.5, color="white", bold=True)
for r, row in enumerate((("h1", "n1", "e1"), ("....", "....", "...."), ("hk", "nk", "ek"))):
    for (x0, w, _), v in zip(cols, row):
        box(tx + x0, ty + 5.1 - r * 2.5, w, 2.5, v, fc="#dae3f3", ec="#9db3dc", fs=8)
ax.text(tx + 28.5, ty + 10.3, "Rule A: evictions ≥ 3 × median host", fontsize=8.6, va="center")
ax.text(tx + 28.5, ty + 7.3, "Rule B: occupancy ≥ TH2 and", fontsize=8.6, va="center")
ax.text(tx + 28.5, ty + 5.1, "entries > X and ≥ 3 × median host", fontsize=8.6, va="center")
num(tx - 0.3, ty + 12, 14)
arrow(77.5, 18.6, 77.5, 30.5)

box(81, 22.6, 16.5, 5.2, "Action: block host\n(drop rule, 60-240 s)", fc=RED, ec="#7f0000", fs=9)
arrow(89.25, 30.5, 89.25, 27.8)
num(81.4, 22.6, 15)
box(76, 3.2, 21.5, 5.2, "Fair-share trimming\nper port (≥ TH2 = 90 %)", fc="#f2f2f2", ec=GREY, fs=9)
line([(97.5, 39), (99, 39), (99, 5.8)])
arrow(99, 5.8, 97.5, 5.8)
num(76.4, 3.2, 16)

ax.text(3, 12.5, "SDN controller (Ryu)", fontsize=11, color="#c00000", weight="bold")
ax.text(3, 9.6, "OpenFlow switch: flow table\n3,500 entries, idle timeout 10 s", fontsize=9, color="#404040", va="top")

for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_working.{ext}", dpi=200, facecolor="white")
print("docs/fever_working.png")
