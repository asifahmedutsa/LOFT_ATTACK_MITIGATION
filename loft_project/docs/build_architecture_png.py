"""Builds docs/ensguard_architecture.png: the current system (EnsGuard v5) on one page.
Values match results/v21/exported/ens_config_v5.json, loftbench/defenses.py (EvictBlock) and
testbed/loft_ryu_app.py. The v3 version of this figure is in git history (before 2026-11-07)."""
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


ax.text(80, 108, "EnsGuard v5: federated detection, eviction and blocking against low-rate "
        "flow-table overflow", ha="center", va="center", fontsize=17, weight="bold", color=INK)
ax.text(80, 104.4, "Offline: three SDN controllers build a shared CatBoost ensemble by model sharing.   "
        "Online: each controller runs the same loop on its switch every 1 s poll.",
        ha="center", va="center", fontsize=11, color=MUTED)

# ---- Offline federation (top band) ----
box(4, 74.6, 152, 25.9, "gray", r=2.2, lw=1.0)
ax.text(7, 98, "OFFLINE  ·  FEDERATED TRAINING (model sharing, no raw flow data leaves a domain)",
        fontsize=10.5, weight="bold", color=C["gray"][1], va="center")
for i, (d, seen) in enumerate((("D1", "A1, A4"), ("D2", "A2, A5"), ("D3", "A3, A7"))):
    x = 8 + i * 34
    e = box(x, 79, 30, 16, "blue")
    ax.text(x + 15, 92, f"Controller {d}", ha="center", fontsize=11.5, weight="bold", color=e)
    ax.text(x + 15, 87.6, f"local flow-entry data:\nits own benign traffic + attacks {seen}", ha="center",
            va="center", fontsize=9, color=INK)
    ax.text(x + 15, 82.4, "trains one CatBoost model\non 17 features",
            ha="center", va="center", fontsize=9, color=INK)
    ax.plot([x + 15, x + 15], [79, 77.6], color=C["blue"][1], lw=1.4)
ax.plot([23, 108], [77.6, 77.6], color=C["blue"][1], lw=1.4)
ax.plot([108, 108], [77.6, 87], color=C["blue"][1], lw=1.4)
arrow(108, 87, 110, 87, col=C["blue"][1], lw=1.4)
ax.text(64, 76.3, "each controller uploads its trained models (not its data)", ha="center",
        fontsize=8.8, color=C["blue"][1], va="center")
e = box(110, 79, 42, 16, "purp")
ax.text(131, 92, "Shared ensemble", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(131, 86.2, "score = mean P(attack) of the 3 CatBoost models\n"
        "each domain sets its own τ at a 0.1 % benign-flag budget\n"
        "testbed, from T1A traffic only: τ = 0.620 and\nvolume limit X = 1.5 × busiest benign host\n"
        "(785-800 entries per switch)",
        ha="center", va="center", fontsize=8.8, color=INK, linespacing=1.3)
arrow(131, 79, 131, 70.5, col=C["purp"][1], lw=2)
ax.text(133, 72.6, "same model deployed to every controller", fontsize=9, color=C["purp"][1],
        va="center")

# ---- Online loop (per controller) ----
ax.text(7, 71, "ONLINE  ·  EACH CONTROLLER, EVERY 1 s FLOW-STATS POLL", fontsize=10.5,
        weight="bold", color=INK, va="center")
steps = [
    ("blue", "01  Read flow stats", "OpenFlow 1.3 flow-stats reply: per-entry packets, bytes, age,\n"
     "source MAC (host identity) and ingress port; table occupancy"),
    ("teal", "02  Features, changed only", "17 features per entry (11 flow · 3 source host · 3 table);\n"
     "only entries whose counters changed since the last poll are rescored (median 13 ms per poll)"),
    ("purp", "03  Score", "P(attack) per entry from the 3 shared CatBoost models (exact 8-bit scorer);\n"
     "runs only while the table is ≥ 70 % full (ρ = 0.7) or a host is on probation"),
    ("amber", "04  Evict", "delete every entry with score ≥ τ  (frees the slots the low-rate "
     "attacker refreshes)"),
    ("coral", "05  Block rule A: detector", "a host whose evictions in the last 10 s are ≥ 50, ≥ 3 × max(median host, 10)\n"
     "and ≥ 20 % of its own entries — catches attacks the model recognises (A2)"),
    ("coral", "06  Block rule B: volume", "NEW in v5, no ML: at ≥ 90 % occupancy, a host holding > X entries and ≥ 3 × the\n"
     "median host's — catches disguised attacks the model misses (A4, E9P)"),
    ("red", "07  PortGuard fallback", "at ≥ 90 % occupancy: weighted max-min fair share of the "
     "table per access port\n(quota, trim the highest-scoring entries first) — bounds any attacker "
     "both rules miss"),
]
y0, h, gap = 62.0, 7.2, 1.25
for i, (col, title, desc) in enumerate(steps):
    y = y0 - i * (h + gap)
    e = box(6, y, 40, h, col)
    ax.text(8.5, y + h / 2, title, fontsize=12, weight="bold", color=e, va="center")
    box(48, y, 74, h, col, lw=0.8)
    ax.text(50.5, y + h / 2, desc, fontsize=9.6, color=INK, va="center", linespacing=1.35)
    if i < len(steps) - 1:
        arrow(26, y, 26, y - gap, col=MUTED, lw=1.4)
yb = y0 - (len(steps) - 1) * (h + gap)
ax.text(64, yb - 2.6, "Rule A or B: drop rule by MAC for 60 s, doubling on repeat "
        "(at most 240 s), then 20 s probation", ha="center", fontsize=9.2, color=C["coral"][1], style="italic")

# Switch / outcome on the right
e = box(126, 34, 30, 26.7, "gray", lw=1.2)
ax.text(141, 57.8, "OpenFlow switch", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(141, 46.5, "flow table\n(3500 entries,\nidle timeout 10 s)\n\nreactive per-5-tuple\n"
        "rules from Packet-In", ha="center", va="center", fontsize=9.2, color=INK, linespacing=1.3)
arrow(126, 56, 122, 64.6, col=C["blue"][1], lw=1.4)
ax.text(123.2, 61.5, "stats", fontsize=8.5, color=C["blue"][1], rotation=0)
for yy in (y0 - 3 * (h + gap) + h / 2, y0 - 4 * (h + gap) + h / 2, y0 - 5 * (h + gap) + h / 2, yb + h / 2):
    arrow(122, yy, 126, max(min(yy, 58), 36), col=C["red"][1], lw=1.2)
ax.text(141, 30.5, "delete · drop rule · quota", ha="center", fontsize=9, color=C["red"][1])

e = box(126, 10, 30, 17, "teal", lw=1.2)
ax.text(141, 24.2, "Outcome", ha="center", fontsize=11.5, weight="bold", color=e)
ax.text(141, 17.4, "testbed, unseen traffic (T1B):\nbenign harm 0.49 %\nattacker share 22 %\n"
        "attackers blocked in 15/15 runs\nno innocent host blocked", ha="center", va="center", fontsize=9.2,
        color=INK, linespacing=1.3)

ax.text(80, 1.4, "Testbed: Mininet + Open vSwitch + Ryu, tree topology (core s11, edge s12/s13) per "
        "controller; the controller runs the same defense code as the simulator.",
        ha="center", fontsize=8.8, color=MUTED, style="italic")

fig.savefig("docs/ensguard_architecture.png", dpi=150, facecolor=fig.get_facecolor())
print("docs/ensguard_architecture.png")
