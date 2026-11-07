"""Builds docs/fever_federated_training.{png,pdf}: one round of FEVER's federated training. Each
controller trains a CatBoost model on its own flow entries (1) and uploads only the model to the
federated server (2); the server aggregates the three models into the shared detector, which scores
an entry by the mean of the three models' attack probabilities (3), and sends it back to every
controller (4). Each controller then sets its own threshold on its benign traffic.

    ~/.venvs/loft/bin/python docs/build_fed_training_fig.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Rectangle  # noqa: E402

plt.rcParams.update({"font.family": "Liberation Serif", "font.size": 10})
K, GREY = "#000000", "#9a9a9a"
UP, DOWN = "#c0504d", "#2f6fd0"

fig = plt.figure(figsize=(10, 7.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 74)
ax.axis("off")


def server(cx, cy, w=4.6, h=6.6, fc="#d6e3f5", ec="#2f5597"):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc=fc, ec=ec, lw=1.2))
    for k in range(4):
        ax.plot([cx - w / 2 + 0.8, cx + w / 2 - 0.8], [cy + h / 2 - 1.3 - k * 1.2] * 2, color=ec, lw=0.9)


def database(cx, cy, label):
    for dy in (0, -1.2, -2.4):
        ax.add_patch(Ellipse((cx, cy + dy), 6, 1.6, fc="#eeeeee", ec="#555555", lw=0.9))
    ax.add_patch(Rectangle((cx - 3, cy - 2.4), 6, 2.4, fc="#eeeeee", ec="none"))
    ax.plot([cx - 3, cx - 3], [cy - 2.4, cy], color="#555555", lw=0.9)
    ax.plot([cx + 3, cx + 3], [cy - 2.4, cy], color="#555555", lw=0.9)
    ax.add_patch(Ellipse((cx, cy - 2.4), 6, 1.6, fc="#eeeeee", ec="#555555", lw=0.9))
    ax.add_patch(Ellipse((cx, cy), 6, 1.6, fc="#eeeeee", ec="#555555", lw=0.9))
    ax.text(cx, cy - 4.4, label, ha="center", va="top", fontsize=9)


def model(cx, cy, label, fc="#fbe5d6", ec="#c55a11"):
    ax.add_patch(FancyBboxPatch((cx - 6.3, cy - 2), 12.6, 4, boxstyle="round,pad=0,rounding_size=0.8", fc=fc, ec=ec, lw=1.1))
    ax.text(cx, cy, label, ha="center", va="center", fontsize=9.5, weight="bold")


def step(cx, cy, n):
    ax.add_patch(Circle((cx, cy), 1.4, fc="white", ec=K, lw=1.0))
    ax.text(cx, cy, str(n), ha="center", va="center", fontsize=9.5, weight="bold")


# federated server
ax.add_patch(FancyBboxPatch((32, 55), 36, 16, boxstyle="round,pad=0,rounding_size=1.4", fc="none", ec=GREY,
                            lw=1.2, ls=(0, (5, 3))))
server(39, 63)
ax.text(50, 69, "Federated Server", ha="center", fontsize=12, weight="bold")
ax.text(55.5, 64.2, "Aggregation", ha="center", fontsize=10, weight="bold")
ax.text(55.5, 61.2, "shared detector =\nmean of the three models'\nattack probabilities", ha="center", va="top", fontsize=9)
step(65.5, 57.5, 3)

xs = [17, 50, 83]
for i, (x, d, kind, seen) in enumerate(zip(xs, ("D1", "D2", "D3"), ("enterprise", "IoT", "cloud"),
                                          ("A1, A4", "A2, A5", "A3, A7"))):
    ax.add_patch(FancyBboxPatch((x - 15, 3), 30, 31, boxstyle="round,pad=0,rounding_size=1.2", fc="none", ec=GREY,
                                lw=1.1, ls=(0, (5, 3))))
    ax.text(x - 13.5, 31.2, f"Controller {d}\n({kind})", ha="left", va="center", fontsize=11, weight="bold")
    database(x - 7, 25.5, f"flow entries\n(benign, {seen})")
    model(x - 7, 9, f"Local CatBoost M{i + 1}")
    ax.annotate("", xy=(x - 7, 11.1), xytext=(x - 7, 17.6),
                arrowprops=dict(arrowstyle="-|>", color=K, lw=1.0, mutation_scale=10))
    step(x - 3.2, 14.6, 1)
    model(x + 7.5, 9, "Shared detector", fc="#dbe8f7", ec="#2f5597")
    ax.text(x + 7.5, 5.2, "+ local threshold τ", ha="center", fontsize=8.5, style="italic")
    up0, dn1 = (x - 7, 34), (x + 7.5, 34)
    up1 = (36 + i * 10, 55) if i < 2 else (60, 55)
    dn0 = (40 + i * 7, 55) if i < 2 else (64, 55)
    if i == 1:
        up1, dn0 = (45, 55), (55, 55)
    ax.annotate("", xy=up1, xytext=up0, arrowprops=dict(arrowstyle="-|>", color=UP, lw=1.6, mutation_scale=12))
    ax.annotate("", xy=dn1, xytext=dn0,
                arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=1.6, ls="--", mutation_scale=12))
    ax.annotate("", xy=(x + 7.5, 11.1), xytext=(x + 7.5, 34),
                arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=1.0, ls=(0, (2, 2)), mutation_scale=9))
step(17.5, 46, 2)
step(72.5, 46, 4)
ax.text(17.5, 50.5, "upload local model\n(no traffic data)", ha="center", fontsize=9.5, color=UP)
ax.text(82, 50.5, "download\nshared detector", ha="center", fontsize=9.5, color=DOWN)
for ext in ("png", "pdf"):
    fig.savefig(f"docs/fever_federated_training.{ext}", dpi=200, facecolor="white")
print("wrote docs/fever_federated_training.png")
