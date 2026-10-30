"""Builds docs/architecture_explained.pdf: a step-by-step, plain-language guide."""
import sys

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVM", FD + "DejaVuSansMono.ttf"))
from reportlab.lib.fonts import addMapping  # noqa: E402
addMapping("DV", 0, 0, "DV")
addMapping("DV", 1, 0, "DVB")

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#52606d")
TEAL = colors.HexColor("#0f6e56")
TEAL_L = colors.HexColor("#e1f5ee")
PURP = colors.HexColor("#534ab7")
PURP_L = colors.HexColor("#eeedfe")
CORAL = colors.HexColor("#993c1d")
CORAL_L = colors.HexColor("#faece7")
GRAY_L = colors.HexColor("#f1efe8")
GRAY = colors.HexColor("#5f5e5a")
AMBER_L = colors.HexColor("#faeeda")
AMBER = colors.HexColor("#854f0b")

H1 = ParagraphStyle("h1", fontName="DVB", fontSize=17, leading=22, textColor=INK, spaceAfter=8)
H2 = ParagraphStyle("h2", fontName="DVB", fontSize=13, leading=17, textColor=TEAL, spaceBefore=10,
                    spaceAfter=5)
BODY = ParagraphStyle("b", fontName="DV", fontSize=9.6, leading=14, textColor=INK, spaceAfter=5)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=8.4, leading=11.5, textColor=MUTED)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CAP = ParagraphStyle("cap", parent=SMALL, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.6, leading=11.5, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="DVB")
TITLE = ParagraphStyle("t", fontName="DVB", fontSize=24, leading=30, textColor=INK, spaceAfter=6)
SUB = ParagraphStyle("st", parent=BODY, fontSize=11.5, leading=16, textColor=MUTED)
BOX = ParagraphStyle("box", parent=BODY, backColor=TEAL_L, borderColor=TEAL, borderWidth=0.6,
                     borderPadding=7, spaceBefore=6, spaceAfter=10)

W = A4[0] - 4 * cm


def P(t, s=BODY):
    return Paragraph(t, s)


def bullets(items):
    return [Paragraph(i, BUL, bulletText="•") for i in items]


def table(rows, widths, head=True):
    data = [[P(c, CELLB if (head and r == 0) else CELL) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8c6bd")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), GRAY_L))
    t.setStyle(TableStyle(st))
    return t


# ------------------------------------------------------------------ drawing helpers
def box(d, x, y, w, h, title, sub=None, fill=GRAY_L, stroke=GRAY, tc=INK, fs=9):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.7))
    if sub:
        d.add(String(x + w / 2, y + h / 2 + 2, title, fontName="DVB", fontSize=fs, fillColor=tc,
                     textAnchor="middle"))
        d.add(String(x + w / 2, y + h / 2 - 10, sub, fontName="DV", fontSize=fs - 1.5,
                     fillColor=tc, textAnchor="middle"))
    else:
        d.add(String(x + w / 2, y + h / 2 - 3, title, fontName="DVB", fontSize=fs, fillColor=tc,
                     textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, color=GRAY, both=False, dash=None, w=0.9):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=w, strokeDashArray=dash))

    def head(xa, ya, xb, yb):
        import math
        ang = math.atan2(yb - ya, xb - xa)
        s = 5
        p1 = (xb - s * math.cos(ang - 0.45), yb - s * math.sin(ang - 0.45))
        p2 = (xb - s * math.cos(ang + 0.45), yb - s * math.sin(ang + 0.45))
        d.add(Polygon([xb, yb, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color,
                      strokeWidth=0.5))
    head(x1, y1, x2, y2)
    if both:
        head(x2, y2, x1, y1)


def label(d, x, y, t, fs=7.5, color=MUTED, anchor="middle", font="DV"):
    d.add(String(x, y, t, fontName=font, fontSize=fs, fillColor=color, textAnchor=anchor))


def fig_overview():
    d = Drawing(W, 330)
    box(d, W / 2 - 120, 290, 240, 34, "Federated aggregator (FedAvg)", "averages model weights only",
        PURP_L, PURP, PURP)
    xs = [10, W / 2 - 75, W - 160]
    names = [("Controller D1", "enterprise"), ("Controller D2", "IoT"), ("Controller D3", "cloud")]
    for x, (n, s) in zip(xs, names):
        cx = x + 75
        arrow(d, W / 2, 288, cx, 262, PURP, both=True, dash=[3, 2])
        d.add(Rect(x, 150, 150, 110, rx=7, ry=7, fillColor=TEAL_L, strokeColor=TEAL, strokeWidth=0.7))
        label(d, cx, 246, n, 9, TEAL, font="DVB")
        label(d, cx, 235, s, 7.5, TEAL)
        for i, t in enumerate(["1. read flow stats", "2. compute 17 features",
                               "3. score with detector", "4. DualGuard + PortGuard"]):
            label(d, x + 10, 218 - 15 * i, t, 7.8, INK, "start")
        arrow(d, cx, 148, cx, 122, GRAY, both=True)
        box(d, x + 10, 84, 130, 36, "OpenFlow switch", "table: 3,500 entries")
        arrow(d, cx, 58, cx, 82, GRAY)
        box(d, x + 10, 22, 130, 34, "6 hosts", "4 users + 2 attackers", CORAL_L, CORAL, CORAL)
    label(d, 10, 4, "Dashed purple: model weights travel between controllers; raw traffic never "
          "leaves its domain.", 7.5, MUTED, "start")
    return d


def fig_tick():
    d = Drawing(W, 150)
    box(d, 0, 95, 92, 34, "Packet arrives", None, CORAL_L, CORAL, CORAL, 8.5)
    arrow(d, 92, 112, 116, 112)
    box(d, 118, 95, 100, 34, "Entry in table?", None, fs=8.5)
    arrow(d, 218, 112, 246, 112)
    label(d, 232, 117, "yes", 7)
    box(d, 248, 95, 120, 34, "Forward packet", "update counters", TEAL_L, TEAL, TEAL, 8.5)
    arrow(d, 168, 95, 168, 72)
    label(d, 176, 82, "no", 7, anchor="start")
    box(d, 112, 38, 112, 34, "Packet-In", "ask the controller", PURP_L, PURP, PURP, 8.5)
    arrow(d, 224, 55, 250, 55)
    box(d, 252, 38, 100, 34, "Room in table?", None, fs=8.5)
    arrow(d, 352, 62, 380, 80)
    label(d, 360, 76, "yes", 7)
    box(d, 382, 72, 92, 34, "Install entry", "idle timeout 10 s", TEAL_L, TEAL, TEAL, 8.5)
    arrow(d, 352, 48, 380, 30)
    label(d, 360, 32, "no", 7)
    box(d, 382, 6, 92, 34, "TABLE_FULL", "slow path = harm", CORAL_L, CORAL, CORAL, 8.5)
    return d


def fig_poll():
    d = Drawing(W, 70)
    steps = [("Flow stats", "every 1 s"), ("17 features", "per entry"), ("Detector", "score 0-1"),
             ("Threshold", "1 % budget"), ("Policy", "demote / trim")]
    bw, gap = 78, (W - 5 * 78) / 4
    for i, (a, b) in enumerate(steps):
        x = i * (bw + gap)
        fill, st, tc = (TEAL_L, TEAL, TEAL) if i == 4 else (GRAY_L, GRAY, INK)
        box(d, x, 18, bw, 40, a, b, fill, st, tc, 8.5)
        if i < 4:
            arrow(d, x + bw + 2, 38, x + bw + gap - 2, 38)
    return d


def fig_demote():
    d = Drawing(W, 130)
    x0, x1 = 110, W - 10
    sc = (x1 - x0) / 20.0
    label(d, 0, 98, "Normal 10 s timeout", 8.5, INK, "start", "DVB")
    label(d, 0, 87, "slot held 100 %", 7.5, MUTED, "start")
    d.add(Rect(x0, 84, 20 * sc, 16, fillColor=CORAL_L, strokeColor=CORAL, strokeWidth=0.6))
    label(d, 0, 52, "After demotion (1 s)", 8.5, INK, "start", "DVB")
    label(d, 0, 41, "slot held ~20 %", 7.5, MUTED, "start")
    for k in range(4):
        x = x0 + 5 * k * sc
        for y in (106, 60):
            d.add(Rect(x - 2.5, y - 2.5, 5, 5, fillColor=CORAL, strokeColor=CORAL))
        d.add(Rect(x, 38, 1 * sc, 16, fillColor=CORAL_L, strokeColor=CORAL, strokeWidth=0.6))
    d.add(Line(x0, 26, x1, 26, strokeColor=GRAY, strokeWidth=0.5))
    for s in range(0, 21, 5):
        label(d, x0 + s * sc, 15, f"{s} s", 7.5)
    label(d, x0, 2, "Square = one attacker packet (every 5 s). Bar = time the entry occupies a "
          "table slot.", 7.5, MUTED, "start")
    return d


def fig_ports():
    d = Drawing(W, 175)
    vals = [280, 270, 650, 230, 1700, 1700]
    after = [280, 270, 650, 230, 830, 830]
    names = ["port 1", "port 2", "port 3", "port 4", "attacker A", "attacker B"]
    base, top = 28, 160
    sc = (top - base) / 1800.0
    bw = 44
    gap = (W - 60 - 6 * bw) / 5
    for i, (v, a, n) in enumerate(zip(vals, after, names)):
        x = 50 + i * (bw + gap)
        att = i >= 4
        d.add(Rect(x, base, bw, v * sc, fillColor=colors.white,
                   strokeColor=CORAL if att else TEAL, strokeWidth=0.7, strokeDashArray=[2, 2]))
        d.add(Rect(x, base, bw, a * sc, fillColor=CORAL_L if att else TEAL_L,
                   strokeColor=CORAL if att else TEAL, strokeWidth=0.7))
        label(d, x + bw / 2, base - 11, n, 7.5, CORAL if att else TEAL)
        if att:
            label(d, x + bw / 2, base + v * sc + 3, "wants 1,700", 7, CORAL)
    yq = base + 830 * sc
    d.add(Line(40, yq, W - 4, yq, strokeColor=PURP, strokeWidth=0.9, strokeDashArray=[4, 2]))
    label(d, 44, yq + 3, "fair level L", 7.5, PURP, "start", "DVB")
    label(d, 0, base, "0", 7, MUTED, "start")
    label(d, 0, base + 1000 * sc - 3, "1000", 7, MUTED, "start")
    label(d, 50, 2, "Solid bar: entries kept. Dashed outline: what the port asked for.", 7.5,
          MUTED, "start")
    return d


def fig_seeds():
    d = Drawing(W, 92)
    segs = [("Train", "1000-1004", TEAL_L, TEAL), ("Validate", "2000-2002", AMBER_L, AMBER),
            ("Offline test", "3000-3004", GRAY_L, GRAY), ("v2 test", "4000-4009", GRAY_L, GRAY),
            ("v2.1 test", "5000-5009", GRAY_L, GRAY), ("Step 4 test", "6000-6009", CORAL_L, CORAL),
            ("Step 3 test", "7000-7009", PURP_L, PURP)]
    bw = (W - 6 * 6) / 7
    for i, (a, b, f, s) in enumerate(segs):
        box(d, i * (bw + 6), 40, bw, 38, a, b, f, s, s, 8)
    label(d, 0, 22, "Every block is a separate range of random seeds, so no test traffic is ever "
          "seen while training or choosing settings.", 7.8, INK, "start")
    label(d, 0, 9, "Settings are chosen on validation seeds only; each test range is used exactly "
          "once, after the choice is committed to git.", 7.8, INK, "start")
    return d


def fig_caption(d, text):
    return KeepTogether([d, P(text, CAP)])


# ------------------------------------------------------------------ content
def build(path):
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="FL-DualGuard architecture, step by step",
                            author="LOFT attack mitigation project")
    s = []
    s += [Spacer(1, 30), P("FL-DualGuard, step by step", TITLE),
          P("How our multi-controller defense against low-rate flow-table overflow (LFTO) attacks "
            "is built, explained in plain language.", SUB), Spacer(1, 14)]
    s.append(P("<b>How to read this guide.</b> Steps 1–3 explain the problem and the test "
               "environment. Steps 4–9 follow one second of the controller's life, from reading "
               "the switch to acting on it. Steps 10–11 explain how we measure and test fairly. "
               "The last pages map every step to the code and list the results so far.", BOX))
    s.append(P("The whole system on one page", H2))
    s.append(fig_caption(fig_overview(), "Figure 1. Three network domains, each with its own "
                         "controller and switch. Controllers learn together by sharing model "
                         "weights, never traffic."))
    s += bullets([
        "<b>Domains.</b> Three networks with different traffic: an enterprise (D1), an IoT edge "
        "with many periodic sensor flows (D2), and a cloud front-end with flash crowds (D3).",
        "<b>Switch.</b> Each domain has an OpenFlow switch whose flow table holds 3,500 entries. "
        "One entry is needed per active connection.",
        "<b>Controller.</b> Once a second it reads the table, scores every entry with a small "
        "neural network, and decides what to do.",
        "<b>Aggregator.</b> During training, the controllers average their neural-network "
        "weights (federated learning), so each one learns attacks it never saw itself.",
    ])
    s.append(PageBreak())

    # Step 1
    s.append(P("Step 1 — The problem: filling the table slowly", H1))
    s.append(P("A switch forwards a packet quickly only if a matching entry is in its flow table. "
               "The table is small (3,500 entries here), and an entry is removed after 10 seconds "
               "without traffic (the <i>idle timeout</i>)."))
    s.append(P("A low-rate attacker opens thousands of fake connections and sends one tiny packet "
               "on each of them every 5–9.5 seconds. That is just often enough to keep every fake "
               "entry alive. The attack adds about 100 new fake entries every few seconds until "
               "each attacker holds 1,700. The table fills up, and new connections from real "
               "users are refused, even though the attacker sends very little traffic and looks "
               "harmless to a bandwidth monitor."))
    s.append(P("We use the same attack recipe as the DMS-BTT paper (Tang et al., 2025) and add "
               "harder variants:"))
    s.append(table([
        ["Variant", "What it does", "Seen in training?"],
        ["A1–A3", "The three DMS-BTT settings (refresh every 5–9.5 s, 75/100/125 new flows per "
                  "burst, 1,700 flows per attacker)", "A1 by D1, A2 by D2, A3 by D3"],
        ["A4 mimic", "Copies normal packet sizes and sends 1–3 packets per refresh", "D1"],
        ["A5 spoof", "Fakes a random source IP on every flow", "D2"],
        ["A6 slow-fill", "Very slow, spoofed, mimicking", "Never (a \"zero-day\")"],
        ["A7 pulse", "Attacks for 60 s, pauses 30 s, repeats", "D3"],
        ["Fast-refresh (step 4)", "Refreshes every 0.25–1 s to defeat demotion", "Never"],
    ], [2.6 * cm, 10.2 * cm, 4.2 * cm]))

    # Step 2
    s.append(P("Step 2 — Generating traffic", H1))
    s.append(P("Code: <font name='DVM'>loftbench/traffic.py</font>, "
               "<font name='DVM'>config.py</font>, <font name='DVM'>ports.py</font>", SMALL))
    s += bullets([
        "<b>Normal traffic</b> is generated packet by packet from six kinds of flows: DNS "
        "look-ups, short web flows (\"mice\"), large downloads (\"elephants\"), periodic "
        "keep-alives and sensors, interactive sessions, and flash crowds. Each domain mixes them "
        "differently.",
        "<b>Attack traffic</b> follows the recipe in Step 1, with the variant's settings.",
        "<b>Labels come from where a packet came from</b>, never from its features, so the "
        "detector cannot learn a shortcut.",
        "<b>Paired runs.</b> The same random seed always gives the same normal traffic, so every "
        "defense is tested on exactly the same users.",
        "<b>Ports (new in step 4).</b> As in the DMS-BTT topology, each host has its own switch "
        "port: four normal hosts and two attackers. A spoofer can fake its IP address but not the "
        "port it is plugged into.",
    ])
    s.append(PageBreak())

    # Step 3
    s.append(P("Step 3 — The switch simulator", H1))
    s.append(P("Code: <font name='DVM'>loftbench/sim.py</font> (unit-tested in "
               "<font name='DVM'>tests/</font>)", SMALL))
    s.append(P("The simulator replays the traffic in steps of 0.1 seconds and behaves like an "
               "OpenFlow switch:"))
    s.append(fig_caption(fig_tick(), "Figure 2. What happens to each packet in each 0.1 s step."))
    s += bullets([
        "Entries idle for longer than their timeout are removed first.",
        "A packet that matches an entry is forwarded and updates the entry's counters.",
        "A packet with no entry goes to the controller (a <i>Packet-In</i>). If there is room, "
        "the controller installs an entry; if not, the switch reports TABLE_FULL and the packet "
        "takes the slow path through the controller. That is the harm the attack causes.",
        "Every second, the controller reads the table and may delete or demote entries "
        "(Steps 4–9).",
    ])
    s.append(P("The same logic is implemented for a real Ryu controller and Mininet/Open vSwitch "
               "in <font name='DVM'>testbed/</font>; those runs need administrator rights and have "
               "not been run yet."))

    # Steps 4-9
    s.append(P("Steps 4–9 — One second in the life of a controller", H1))
    s.append(fig_caption(fig_poll(), "Figure 3. The controller's loop, repeated every second."))

    s.append(P("Step 4 — Read the flow statistics", H2))
    s.append(P("The controller asks the switch for every entry's packet count, byte count, age "
               "and source address. That is all a standard OpenFlow 1.3 controller can see, so "
               "the method works on real switches."))

    s.append(P("Step 5 — Compute 17 features per entry", H2))
    s.append(P("Code: <font name='DVM'>loftbench/features.py</font>", SMALL))
    s.append(table([
        ["Group", "Features", "What they capture"],
        ["Flow (11)", "packets, bytes, age, mean packet size, packet rate, time between packets, "
                      "new packets since last poll, polls since last activity, share of polls "
                      "active, regularity of gaps, mean gap",
         "Does this entry behave like a fake flow kept barely alive?"],
        ["Source (3)", "entries from the same source, new entries from it in the last 10 s, its "
                       "share of tiny flows", "Is one source opening many small flows?"],
        ["Context (3)", "table occupancy, install rate, average time between packets across the "
                        "table", "Is the table under pressure right now?"],
    ], [2.4 * cm, 9.2 * cm, 5.4 * cm]))
    s.append(PageBreak())

    s.append(P("Step 6 — Score each entry with the detector", H2))
    s.append(P("Code: <font name='DVM'>loftbench/models.py</font>", SMALL))
    s.append(P("The detector is a small neural network (17 inputs → 32 hidden units → 1 output) "
               "that gives every entry a score between 0 (normal) and 1 (attack)."))
    s.append(P("<b>Federated training (FedAvg).</b> Each controller trains on its own traffic, "
               "which contains only two attack variants. Over 30 rounds, the controllers send "
               "their weights to the aggregator, which averages them and sends the result back. "
               "The shared model therefore recognises all variants seen by any controller, while "
               "no traffic records leave a domain. A small model also makes this cheap: about "
               "2.4 KB per controller per round."))
    s.append(P("<b>Why it matters.</b> In step 3 of the revision we tested the alternatives under "
               "the same policy: learning alone harms 7.9 % of normal flows, learning alone plus "
               "the public DMS-BTT attack settings 5.8 %, and federation 1.5 %. Pooling all raw "
               "data gives 1.7 %, so federation matches it without sharing data."))

    s.append(P("Step 7 — Turn scores into decisions with a false-alarm budget", H2))
    s.append(P("A score needs a cut-off. Each controller sets its own cut-off on its own normal "
               "validation traffic so that at most <b>1 % of normal entries</b> would be flagged. "
               "This is the <i>calibration budget</i>. Different domains get different cut-offs, "
               "because their normal traffic differs."))

    s.append(P("Step 8 — DualGuard: demote, don't delete", H2))
    s.append(P("Code: <font name='DVM'>loftbench/defenses.py</font>, class "
               "<font name='DVM'>DualGuard</font>", SMALL))
    s += bullets([
        "<b>Act only under pressure.</b> If the table is less than 70 % full, do nothing.",
        "<b>Demote flagged entries.</b> A flagged entry is removed, and when its next packet "
        "arrives it is reinstalled with a <b>1-second</b> idle timeout instead of 10 seconds.",
        "<b>Why this hurts the attacker.</b> A fake flow refreshed every 5 s now occupies its "
        "slot only about 1 s in 5 (Figure 4), so the table drains.",
        "<b>Why it is gentle on users.</b> A real flow wrongly flagged keeps working: an active "
        "flow sends faster than once a second and never notices; a paused one pays one extra "
        "round trip to the controller.",
    ])
    s.append(fig_caption(fig_demote(), "Figure 4. Demotion shrinks how long a slow attacker holds "
                         "each table slot."))
    s.append(PageBreak())

    s.append(P("Step 9 — PortGuard: a fair share per port (step 4)", H2))
    s.append(P("Code: <font name='DVM'>loftbench/defenses.py</font>, class "
               "<font name='DVM'>PortGuard</font>", SMALL))
    s.append(P("<b>The gap it closes.</b> An attacker who refreshes faster than once a second "
               "keeps even demoted entries alive, and the detector recognises only about 2 % of "
               "its entries because they look like busy normal flows. DualGuard alone then fails "
               "(62 % of normal flows harmed in our check)."))
    s.append(P("<b>The idea.</b> When the table is under pressure, every switch port gets a fair "
               "share of it, computed so that small users keep everything they need and only the "
               "biggest consumers are cut back (max-min fairness):"))
    s.append(fig_caption(fig_ports(), "Figure 5. Ports below the fair level keep all their "
                         "entries; the attackers are cut back to it."))
    s += bullets([
        "Ports above their share are trimmed back, removing their most suspicious entries first "
        "(the detector still chooses which ones).",
        "Those ports are refused new entries until they fall below their share. The controller "
        "counts its own installs, so the limit holds between polls.",
        "<b>Guarantee.</b> Every honest port keeps at least its fair share, however fast the "
        "attacker refreshes, whatever packet sizes it uses and whatever IP addresses it fakes.",
        "<b>Limit.</b> If the attacker controls a host on every port, it gets a fair share on "
        "every port, and PortGuard cannot single it out. The test measures this case on purpose.",
    ])
    s.append(P("<b>Making them cooperate (step 4b).</b> A first combination failed: with the "
               "table held near full, DualGuard kept demoting normal entries and PortGuard gave "
               "the freed slots to the attackers. The final design pauses DualGuard while "
               "PortGuard is enforcing, and weights each port's share by how much of the table "
               "it used while there was no pressure, so busy normal ports are not throttled and "
               "an attacker's port has earned almost nothing.", BODY))
    s.append(P("<b>Test result (fresh seeds, attackers on their own ports).</b> 0.1–0.4 % of "
               "normal flows harmed against attackers refreshing every 0.25–1 s, and at most "
               "3.3 % at any speed, where every learned defense harms 15–81 %. It must be "
               "switched off when the attacker sends from every port: there it raises harm on "
               "the standard attacks from 1.6 % to 8.9 %.", BODY))

    # Steps 10-11
    s.append(PageBreak())
    s.append(P("Step 10 — Measuring what users feel", H1))
    s.append(table([
        ["Metric", "Meaning"],
        ["<b>Normal flows harmed</b> (primary)", "Share of normal connections that were refused "
         "an entry, or removed while still active (their next packet arrived before the entry "
         "would have expired anyway)"],
        ["Malicious occupancy", "Average share of the table held by attack entries"],
        ["Overflow time", "Seconds the table was completely full during the attack"],
        ["Packet-In / TABLE_FULL", "Load on the controller and the control channel"],
    ], [5.2 * cm, 11.8 * cm]))
    s.append(P("<b>Statistics.</b> Each (domain, seed) pair is one independent cluster (30 in the "
               "main tests). We report 95 % confidence intervals by resampling clusters, and "
               "paired Wilcoxon tests with Holm correction. None of the 12 related papers "
               "reports confidence intervals."))

    s.append(P("Step 11 — Testing fairly", H1))
    s.append(fig_caption(fig_seeds(), "Figure 6. Seed ranges used for each purpose."))
    s += bullets([
        "<b>Pre-registration.</b> Before each experiment, the settings to try, the rule for "
        "choosing, the hypotheses and the test seeds are written to a JSON file, hashed and "
        "committed to git.",
        "<b>Validation-only selection.</b> Settings are chosen on validation seeds only.",
        "<b>One-shot test.</b> The chosen settings are run once on fresh seeds; the code refuses "
        "to run a test twice.",
        "<b>Same treatment for baselines.</b> DMS-BTT got the same tuning budget, plus a "
        "blocklist variant, so we compare against its strongest version.",
    ])
    s.append(PageBreak())

    s.append(P("Where each step lives in the code", H1))
    s.append(table([
        ["Step", "File", "Role"],
        ["2", "loftbench/config.py", "Domains, attack variants, simulator settings"],
        ["2", "loftbench/traffic.py, ports.py", "Packet-level traffic, labels, ingress ports"],
        ["3", "loftbench/sim.py", "Bounded flow-table switch with a polling controller"],
        ["4–5", "loftbench/features.py", "17 causal features from flow statistics"],
        ["6–7", "loftbench/models.py", "Neural network, FedAvg/FedProx, calibration"],
        ["8–9", "loftbench/defenses.py", "DualGuard, PortGuard, DMS-BTT, OVS evict, threshold-LRU"],
        ["10", "loftbench/revision1.py", "Harm metric, cluster bootstrap, cluster Wilcoxon"],
        ["11", "loftbench/v21.py, revision2–4.py", "Pre-registration, selection, one-shot tests"],
        ["—", "testbed/", "Ryu app, Mininet topology and traffic drivers (not yet run)"],
        ["—", "tests/test_loftbench.py", "21 unit tests pinning the simulator's behaviour"],
    ], [1.4 * cm, 5.6 * cm, 10.0 * cm]))

    s.append(P("Results so far", H1))
    s.append(table([
        ["Defense (fresh test seeds)", "Normal flows harmed", "Notes"],
        ["No defense", "about 42 %", "The table is full most of the attack"],
        ["DMS-BTT, tuned + blocklist (strongest baseline)", "4.5 %", "Better on its own attack "
         "settings; weak on mimicry (A4) and the unseen A6"],
        ["Each controller learning alone", "7.9 %", "Misses variants seen only elsewhere"],
        ["FL-DualGuard v2.1 (federated)", "1.5 %", "Matches pooling all data; 2.9× fewer harmed "
         "than DMS-BTT"],
        ["Fast attacker (refresh ≤ 1 s): v2.1 alone", "72 %", "The detector does not "
         "recognise it"],
        ["Fast attacker: v2.1 + PortGuard (final)", "0.2 %", "Attackers on their own ports; "
         "same 1.6 % as v2.1 on the standard attacks"],
        ["Same, attacker on every port", "68 %", "Port isolation cannot help; leave PortGuard "
         "off there"],
    ], [6.4 * cm, 3.2 * cm, 7.4 * cm]))
    s.append(Spacer(1, 6))
    s.append(P("<b>Still to do before submission:</b> run the Mininet/Ryu testbed with real "
               "background traces, add the standard comparison table and classifier comparison, "
               "and add the rDefender, FTGuard, SIFT and TableGuard baselines "
               "(see <font name='DVM'>docs/experiments_from_related_work.md</font>).", BODY))

    def footer(c, d_):
        c.saveState()
        c.setFont("DV", 7.5)
        c.setFillColor(MUTED)
        c.drawString(2 * cm, 1.1 * cm, "FL-DualGuard architecture, step by step")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"{d_.page}")
        c.restoreState()

    doc.build(s, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    build(sys.argv[1])
