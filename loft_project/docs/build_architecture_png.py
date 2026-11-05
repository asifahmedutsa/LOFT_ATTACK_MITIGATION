"""Builds docs/ensguard_architecture.png: the current system (FL-EnsGuard) on one page.
Values match results/v21/exported/ens_config.json and testbed/loft_ryu_app.py."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

INK, MUTED = "#1f2933", "#52606d"
C = dict(blue=("#cfe2f7", "#1d5fa8"), teal=("#d3efe6", "#0f6e56"), purp=("#e4e1fb", "#534ab7"),
         amber=("#f8e7c6", "#854f0b"), coral=("#f9ddd3", "#993c1d"), red=("#f6d0cf", "#9b2226"),
         gray=("#ecebe6", "#5f5e5a"))

fig = plt.figure(figsize=(16, 11.2), dpi=150)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 160)
ax.set_ylim(0, 112)
ax.axis("off")
fig.patch.set_facecolor("#fbfbf8")


def box(x, y, w, h, col, r=1.6, lw=1.4):
    fill, edge = C[col]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fill, ec=edge, lw=lw))
    return edge


def arrow(x0, y0, x1, y1, col=MUTED, style="-|>", lw=1.6, ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=14,
                                 color=col, lw=lw, linestyle=ls))


ax.text(80, 108, "FL-EnsGuard: federated detection, eviction and blocking against low-rate "
        "flow-table overflow", ha="center", va="center", fontsize=17, weight="bold", color=INK)
ax.text(80, 104.4, "Offline: three SDN controllers build a shared ensemble by model sharing.   "
        "Online: each controller runs the same loop on its switch every 1 s poll.",
        ha="center", va="center", fontsize=11, color=MUTED)

# ---- Offline federation (top band) ----
box(4, 74.6, 152, 25.9, "gray", r=2.2, lw=1.0)
ax.text(7, 98, "OFFLINE  ·  FEDERATED TRAINING (model sharing, no raw flow data leaves a domain)",
        fontsize=10.5, weight="bold", color=C["gray"][1], va="center")
for i, d in enumerate(("D1", "D2", "D3")):
    x = 8 + i * 34
    e = box(x, 79, 30, 16, "blue")
    ax.text(x + 15, 92, f"Controller {d}", ha="center", fontsize=11.5, weight="bold", color=e)
    ax.text(x + 15, 87.6, "local flow-entry data\n(only the attacks it has seen)", ha="center",
            va="center", fontsize=9, color=INK)
    ax.text(x + 15, 82.2, "trains RF (50 trees, depth 12)\n+ CatBoost on 17 features",
            ha="center", va="center", fontsize=9, color=INK)
    ax.plot([x + 15, x + 15], [79, 77.6], color=C["blue"][1], lw=1.4)
ax.plot([23, 108], [77.6, 77.6], color=C["blue"][1], lw=1.4)
ax.plot([108, 108], [77.6, 87], color=C["blue"][1], lw=1.4)
arrow(108, 87, 110, 87, col=C["blue"][1], lw=1.4)
ax.text(64, 76.3, "each controller uploads its trained models (not its data)", ha="center",
        fontsize=8.8, color=C["blue"][1], va="center")
e = box(110, 79, 42, 16, "purp")
ax.text(131, 92, "Shared ensemble", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(131, 86.4, "score = mean P(attack) of the 6 models\n(3 RF + 3 CatBoost)\n"
        "τ per domain at a 0.1 % benign-flag budget\non validation data (testbed τ = 0.639)",
        ha="center", va="center", fontsize=9, color=INK)
arrow(131, 79, 131, 70.5, col=C["purp"][1], lw=2)
ax.text(133, 72.6, "same model deployed to every controller", fontsize=9, color=C["purp"][1],
        va="center")

# ---- Online loop (per controller) ----
ax.text(7, 71, "ONLINE  ·  EACH CONTROLLER, EVERY 1 s FLOW-STATS POLL", fontsize=10.5,
        weight="bold", color=INK, va="center")
steps = [
    ("blue", "01  Read flow stats", "OpenFlow 1.3 flow-stats reply: per-entry packets, bytes, age,\n"
     "source MAC (host identity) and ingress port; table occupancy"),
    ("teal", "02  17 causal features", "11 flow-level (rate, gaps, sizes) · 3 source-level "
     "(the host's other entries)\n· 3 context-level (table occupancy and churn)"),
    ("purp", "03  Score with the ensemble", "P(attack) per entry from the shared RF + CatBoost "
     "ensemble;\nruns only while the table is ≥ 70 % full (ρ = 0.7) or a host is on probation"),
    ("amber", "04  Evict", "delete every entry with score ≥ τ  (frees the slots the low-rate "
     "attacker refreshes)"),
    ("coral", "05  Block outlier hosts", "a host whose evictions in the last 10 s are ≥ 50 and ≥ 3× "
     "the median host's\nis blocked (drop rule by MAC) 60 s, doubling on repeat, at most 240 s; "
     "then 20 s probation"),
    ("red", "06  PortGuard fallback", "at ≥ 90 % occupancy: weighted max-min fair share of the "
     "table per access port\n(quota, trim the highest-scoring entries first) — bounds any attacker "
     "the model misses"),
]
y0, h, gap = 60.5, 8.2, 1.6
for i, (col, title, desc) in enumerate(steps):
    y = y0 - i * (h + gap)
    e = box(6, y, 40, h, col)
    ax.text(8.5, y + h / 2, title, fontsize=12, weight="bold", color=e, va="center")
    box(48, y, 74, h, col, lw=0.8)
    ax.text(50.5, y + h / 2, desc, fontsize=9.6, color=INK, va="center", linespacing=1.35)
    if i < len(steps) - 1:
        arrow(26, y, 26, y - gap, col=MUTED, lw=1.4)
yb = y0 - (len(steps) - 1) * (h + gap)

# Switch / outcome on the right
e = box(126, 34, 30, 26.7, "gray", lw=1.2)
ax.text(141, 57.8, "OpenFlow switch", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(141, 46.5, "flow table\n(3500 entries,\nidle timeout 10 s)\n\nreactive per-5-tuple\n"
        "rules from Packet-In", ha="center", va="center", fontsize=9.2, color=INK, linespacing=1.3)
arrow(126, 56, 122, 64.6, col=C["blue"][1], lw=1.4)
ax.text(123.2, 61.5, "stats", fontsize=8.5, color=C["blue"][1], rotation=0)
for yy in (y0 - 3 * (h + gap) + h / 2, y0 - 4 * (h + gap) + h / 2, yb + h / 2):
    arrow(122, yy, 126, max(min(yy, 58), 36), col=C["red"][1], lw=1.2)
ax.text(141, 30.5, "delete · drop rule · quota", ha="center", fontsize=9, color=C["red"][1])

e = box(126, 10, 30, 17, "teal", lw=1.2)
ax.text(141, 24.2, "Outcome", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(141, 17.6, "attack entries removed\nbefore the table fills;\nbenign hosts keep their\n"
        "share and new flows\nstill get rules", ha="center", va="center", fontsize=9.2, color=INK,
        linespacing=1.3)

ax.text(80, 1.4, "Testbed: Mininet + Open vSwitch + Ryu, tree topology (core s11, edge s12/s13) per "
        "controller; the controller runs the same defense code as the simulator.",
        ha="center", fontsize=8.8, color=MUTED, style="italic")

fig.savefig("docs/ensguard_architecture.png", dpi=150, facecolor=fig.get_facecolor())
print("docs/ensguard_architecture.png")
